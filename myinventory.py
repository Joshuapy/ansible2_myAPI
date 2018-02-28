#!/usr/bin/env python
# coding:utf8

#import os
from ansible.inventory.manager import InventoryManager as Inventory
from ansible.parsing.dataloader import DataLoader

from ansible.plugins.inventory import BaseInventoryPlugin
from collections import Mapping

from ansible.errors import AnsibleError, AnsibleParserError
from ansible.module_utils.six import iteritems
from ansible.module_utils._text import to_native

__all__ = ["MyInventory"]

HOSTS_PATTERNS_CACHE = {}

class MyInventory(Inventory):
    """
    this is my ansible inventory object.
    支持三种数据类型的主机信息:
        - 字符串形式： "1.1.1.1, 2.2.2.2", "1.1.1.1"
        - 列表形式: ["1.1.1.1", "2.2.2.2"]
        - 字典形式: {
            "group1": {
                "hosts": [{"hostname": "10.10.10.10", "port": "22",
                            "username": "test", "password": "mypass"}, ...]
                "vars": {"var1": value1, "var2": value2, ...}
            }
        }

    注意:
        如果你只传入1个列表，则不能加载主机变量
    """
    def __init__(self, sources=None):
        if sources is not None:
            sources = [sources]

        self.loader = DataLoader()
        self._inventory_plugins = []
        self._inventory_plugins.append(InventoryDictPlugin()) # 添加自己的plugin
        super(MyInventory, self).__init__(self.loader, sources)



class InventoryDictPlugin(BaseInventoryPlugin):
    """
    参照仓库解析插件script做的针对字典类型的数据仓库解析插件.
    Host inventory parser for ansible using Dict data. as inventory scripts.
    """
    def __init__(self):
        super(InventoryDictPlugin, self).__init__()
        self._hosts = set()

    def verify_file(self, sources):
        return isinstance(sources, Mapping)

    def parse(self, inventory, loader, sources, cache=None):
        super(InventoryDictPlugin, self).parse(inventory, loader, sources)

        data_from_meta = None

        try:
            for group, gdata in sources.iteritems():
                if group == "_meta":
                    if "hostvars" in gdata:
                        data_from_meta = gdata['hostvars']
                else:
                    self._parse_group(group, gdata)

            for host in self._hosts:
                got = {}
                if data_from_meta is not None:
                    try:
                        got = data_from_meta.get(host, {})
                    except AttributeError as e:
                        msg = "Improperly formatted host information for {}: {}"
                        raise AnsibleError(msg.format(host, to_native(e)))

                self._populate_host_vars([host], got)

        except Exception as e:
            raise AnsibleParserError(to_native(e))

    def _parse_group(self, group, data):

        self.inventory.add_group(group)

        if not isinstance(data, dict):
            data = {'hosts': data}
        elif not any(k in data for k in ('hosts', 'vars', 'children')):
            data = {'hosts': [group], 'vars': data}

        if 'hosts' in data:
            if not isinstance(data['hosts'], list):
                raise AnsibleError("You defined a group '%s' with bad data for the host list:\n %s" % (group, data))

            for hostname in data['hosts']:
                self._hosts.add(hostname)
                self.inventory.add_host(hostname, group)

        if 'vars' in data:
            if not isinstance(data['vars'], dict):
                raise AnsibleError("You defined a group '%s' with bad data for variables:\n %s" % (group, data))

            for k, v in iteritems(data['vars']):
                self.inventory.set_variable(group, k, v)

        if group != '_meta' and isinstance(data, dict) and 'children' in data:
            for child_name in data['children']:
                self.inventory.add_group(child_name)
                self.inventory.add_child(group, child_name)


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
