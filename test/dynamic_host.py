#! /usr/bin/env python
# coding:Utf8

"""
hosts       主机列表
children    子组
hostvars    主机变量
vars        组变量
"""

import sys
import json
import argparse



inventory = {
    "test":{
        "hosts":['172.16.6.222'],
        "vars":{
            "ansible_ssh_user":"root",
            "ansible_ssh_pass":"8ql6,yhY",
            "host": "wanghua",
            "port": 23,
            "user": "root",
            "passwd": "123"
            },
        "children": ['211','210']
    },
    "211":{
        "ansible_ssh_host": "172.16.8.211"
        },
    "172.16.8.210":{
        "ansible_ssh_user":"root",
        "ansible_ssh_pass":"8ql6,yhY",
    },
    "_meta":{
        "hostvars":{
            "211":{
                "ansible_ssh_user":"root",
                "ansible_ssh_pass":"8ql6,yhY",
            },
        },
    }
}



def init_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", default=True, dest="list" ,help="show all hosts list")
    parser.add_argument("--host", action="store", dest="host" ,help="show specify hosts info")
    return parser.parse_args()


if __name__ == "__main__":
    args = init_args()
    json_data = json.dumps({})
    if args.host:
        json_data = json.dumps(inventory['_meta']['hostvars'].get(args.host, {}))
    elif args.list:
        json_data = json.dumps(inventory, indent=4)
    print json_data
