#!/usr/bin/env python
# coding:utf8

import sys
sys.path.append("../")

from runner import Runner
from pprint import pprint

host_dict = {
    "group1": {
        'hosts': ["172.16.8.210", ],
        'vars': {'host': 'var_value'}
    },
    "_meta": {
        "hostvars": {
            "172.16.8.210": {"hosts": "hostvalue"}
        }
    }
}

runner = Runner(
    # module_name="template",
    # module_args="src=./test.j2 dest=/home/gjobs_test/test.j2",
    module_name="ping",
    # module_args="uptime",
    pattern="all",
    remote_user="root",
    hosts=host_dict,

    private_key_file="/home/joshua/.ssh/id_rsa_gjobs",
    passwords={"conn_pass": "8ql6,yhY"},
    connection_type="paramiko",
    timeout=5
    # extra_vars=["k=v","k2=v2"],
    # hosts=["11.1.1.1"]
)

pprint(runner.run())
