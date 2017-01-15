#!/usr/bin/env python
# coding:utf8

import os
from ansible.inventory import Inventory
from ansible.inventory.host import Host
from ansible.inventory.group import Group
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.compat.six import string_types
from ansible.parsing.utils.addresses import parse_address
from ansible.utils.vars import combine_vars
from ansible.inventory.dir import InventoryDirectory, get_file_parser
from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.utils.unicode import to_unicode, to_str
from ansible.plugins import vars_loader
from ansible.compat.six import iteritems


__all__ = ["MyInventory", ]

HOSTS_PATTERNS_CACHE = {}

class MyInventory(Inventory):
    """
    this is my ansible inventory object.
    """
    def __init__(self, host_list=None):
        """
        host_list的数据格式是一个列表字典，比如
            {
                "group1": {
                    "hosts": [{"hostname": "10.10.10.10", "port": "22",
                                "username": "test", "password": "mypass"}, ...]
                    "vars": {"var1": value1, "var2": value2, ...}
                }
            }

        如果你只传入1个列表，则不能加载主机变量
            ['1.1.1.1', '2.2.2.2'...]
            or
            "1.1.1.1,"
            or
            "1.1.1.1,2.2.2.2"
        """
        self.host_list = host_list or []
        self.loader = DataLoader()
        self.variable_manager = VariableManager()
        super(MyInventory, self).__init__(self.loader, self.variable_manager, host_list=[])
        self.clear_pattern_cache()

        # perform my `parse_inventory()`
        self.parse_inventory(host_list)

    def parse_inventory(self, host_list):

        if isinstance(host_list, string_types):
            if "," in host_list:
                host_list = [ h.strip() for h in host_list.split(',') if h and h.strip() ]
            else:
                host_list = [ host_list ]


        self.parser = None

        # Always create the 'all' and 'ungrouped' groups, even if host_list is
        # empty: in this case we will subsequently an the implicit 'localhost' to it.

        ungrouped = Group('ungrouped')
        all = Group('all')
        all.add_child_group(ungrouped)

        self.groups = dict(all=all, ungrouped=ungrouped)

        if host_list is None:
            pass

        elif isinstance(host_list, list):
            for h in host_list:
                try:
                    (host, port) = parse_address(h, allow_ranges=False)
                except AnsibleError as e:
                    raise AnsibleError("Unable to parse address from hostname, leaving unchanged: %s" % to_unicode(e))
                else:
                    host = h
                    port = None

                new_host = Host(host, port)
                if h in C.LOCALHOST:
                    # set default localhost from inventory to avoid creating an implicit one. Last localhost defined 'wins'.
                    if self.localhost is not None:
                        raise AnsibleError("A duplicate localhost-like entry was found (%s). First found localhost was %s" % (h, self.localhost.name))
                    # display.vvvv("Set default localhost to %s" % h)
                    self.localhost = new_host
                all.add_host(new_host)

        # custom use InventoryDictParser()
        elif isinstance(host_list, dict):
            self.parser = InventoryDictParser(loader=self._loader, groups=self.groups, dictdata=host_list)

        elif self._loader.path_exists(host_list):
            #TODO: switch this to a plugin loader and a 'condition' per plugin on which it should be tried, restoring 'inventory pllugins'
            if self.is_directory(host_list):
                # Ensure basedir is inside the directory
                host_list = os.path.join(self.host_list, "")
                self.parser = InventoryDirectory(loader=self._loader, groups=self.groups, filename=host_list)
            else:
                self.parser = get_file_parser(host_list, self.groups, self._loader)
                vars_loader.add_directory(self._basedir, with_subdir=True)

            if not self.parser:
                # should never happen, but JIC
                raise AnsibleError("Unable to parse %s as an inventory source" % host_list)
        else:
            raise AnsibleError(
                    "host_list parse error, please correct your data source")

        self._vars_plugins = [ x for x in vars_loader.all(self) ]

        # set group vars from group_vars/ files and vars plugins
        for g in self.groups:
            group = self.groups[g]
            group.vars = combine_vars(group.vars, self.get_group_variables(group.name))

        # get host vars from host_vars/ files and vars plugins
        for host in self.get_hosts(ignore_limits=True, ignore_restrictions=True):
            host.vars = combine_vars(host.vars, self.get_host_variables(host.name))
            self.get_host_vars(host)


class InventoryDictParser(object):
    """
    Host inventory parser for ansible using Dict data. as inventory scripts.
    """
    def __init__(self, loader, groups=None, dictdata=None):
        self._loader = loader
        self.groups = groups or {}
        self.dictdata = dictdata
        self.host_vars_from_top = None
        self._parse()

    def _parse(self):
        all_hosts = {}

        group = None
        for (group_name, data) in self.dictdata.items():

            if group_name == '_meta':
                if 'hostvars' in data:
                    self.host_vars_from_top = data['hostvars']
                    continue

            if group_name not in self.groups:
                self.groups[group_name] = Group(group_name)

            group = self.groups[group_name]
            host = None

            # struct_1  "group": [ip1, ip2, ...]
            if not isinstance(data, dict):
                data = {'hosts': data}
            # struct_2  "ip": {'var':'value1', ...}
            # is not those subkeys, then simplified syntax, host with vars
            elif not any(k in data for k in ('hosts', 'vars', 'children')):
                data = {'hosts': [group_name], 'vars': data}

            if 'hosts' in data:
                if not isinstance(data['hosts'], list):
                    raise AnsibleError("You defined a group \"%s\" with bad "
                        "data for the host list:\n %s" % (group_name, data))

                for hostname in data['hosts']:
                    if hostname not in all_hosts:
                        all_hosts[hostname] = Host(hostname)
                    host = all_hosts[hostname]
                    group.add_host(host)

            if 'vars' in data:
                if not isinstance(data['vars'], dict):
                    raise AnsibleError("You defined a group \"%s\" with bad "
                        "data for variables:\n %s" % (group_name, data))

                for k, v in iteritems(data['vars']):
                    group.set_variable(k, v)

        # Separate loop to ensure all groups are defined
        for (group_name, data) in self.dictdata.items():
            if group_name == '_meta':
                continue
            if isinstance(data, dict) and 'children' in data:
                for child_name in data['children']:
                    if child_name in self.groups:
                        self.groups[group_name].add_child_group(self.groups[child_name])

        # Finally, add all top-level groups as children of 'all'.
        # We exclude ungrouped here because it was already added as a child of
        # 'all' at the time it was created.

        for group in self.groups.values():
            if group.depth == 0 and group.name not in ('all', 'ungrouped'):
                self.groups['all'].add_child_group(group)



    def get_host_variables(self, host):
        if self.host_vars_from_top is None:
            return dict()
        else:
            try:
                got = self.host_vars_from_top.get(host.name, {})
            except AttributeError as e:
                raise AnsibleError("Improperly formated host information for %s: %s" % (host.name,to_str(e)))
            return got


if __name__ == "__main__":
    host_list = {
        "group1": ['1.1.1.1'],
        "group2": {
            "hosts": ["2.2.2.2"],
            "vars": {"var2": "var_value2"}
        },
        "3.3.3.3":{
            "ansible_ssh_host": "3.3.3.3",
            "3vars": "3value"
            },
        "_meta":{"hostvars":{}}
    }

    host_list1 = "1.1.1.1"
    host_list2 = ["1.1.1.1","2.2.2.2"]

    hosts_source = host_list
    myhosts = MyInventory(hosts_source)

    print "groups:", myhosts.list_groups()
    print "all.child_groups:", myhosts.groups["all"].child_groups
    print "all:", myhosts.list_hosts("all")
    print "*:", myhosts.list_hosts("*")

    print "all group hosts:", myhosts.groups["all"].get_hosts()
    print "pattern_cache:", myhosts._pattern_cache

    if isinstance(hosts_source, dict):
        print "group1:", myhosts.list_hosts("group1")
        print "group2:", myhosts.list_hosts("group2")

        print "group1 vars:", myhosts.get_group_vars(myhosts.groups["group1"])
        print myhosts.groups["group1"].vars

        print "group2 vars:", myhosts.get_group_vars(myhosts.groups["group2"])
        print myhosts.groups["group2"].vars
