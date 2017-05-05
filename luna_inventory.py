#!/usr/bin/env python

'''
Example custom dynamic inventory script for Ansible, in Python.
'''

import os
import sys
import argparse

import luna
try:
    import json
except ImportError:
    import simplejson as json

class LunaInventory(object):

    def __init__(self):
        self.inventory = {}
        self.read_cli_args()

        # Called with `--list`.
        if self.args.list:
            self.inventory = self.luna_inventory()
        # Called with `--host [hostname]`.
        elif self.args.host:
            # Not implemented, since we return _meta info `--list`.
            self.inventory = self.empty_inventory()
        # If no groups or vars are present, return an empty inventory.
        else:
            self.inventory = self.empty_inventory()

        print json.dumps(self.inventory);

    def luna_inventory(self):
        inventory = {}
        osimages = {'hosts':[],'vars': {'ansible_connection': 'lchroot'}}
        for osimage in luna.list('osimage'):
            #osimages['hosts'].append(luna.OsImage(osimage).get('path'))
            osimages['hosts'].append(osimage)

        inventory['osimages'] = osimages
        nodes = {}
        for n in luna.list('node'):
            node = luna.Node(n).show()
            group = node['group'].replace("[","").replace("]","")
            if group in inventory:
                inventory[group]['hosts'].append(node['name'])
            else:
                inventory[group] = {'hosts':[node['name']], 'vars': {}}
        return inventory
    # Empty inventory for testing.
    def empty_inventory(self):
        return {'_meta': {'hostvars': {}}}

    # Read the command line args passed to the script.
    def read_cli_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--list', action = 'store_true')
        parser.add_argument('--host', action = 'store')
        self.args = parser.parse_args()

# Get the inventory.
LunaInventory()
