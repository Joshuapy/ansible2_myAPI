#!/usr/bin/env python
# coding:utf8

import sys
sys.path.append("../")

from runner import Runner
from pprint import pprint

host_dict = {
    "group1": {
        'hosts': ["192.168.1.100", "1.1.1.1", "192.168.70.39"],
        'vars': {'host': 'var_value'}
    },
    "_meta": {
        "hostvars": {
            "192.168.1.100": {"hosts": "hostvalue"}
        }
    }
}

runner = Runner(
    module_name="shell",
    module_args="uptime",
    remote_user="root",
    pattern="all",
    hosts=host_dict,
)

pprint(runner.run())
