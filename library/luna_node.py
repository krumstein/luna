#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pycompat24 import get_exception
import json
import luna
import sys

def luna_node_present(data):
        name = data['name']
        group = data['group']
        interfaces = data['interfaces']
        mac = data['mac']
        switch = data['switch']
        port = data['port']
        localboot = data['localboot'] 
        service = data['service'] 
        setupbmc = data['setupbmc'] 
        comment = data['comment']
        
        nodes = luna.list('node')
        msg = ""
    #    try:
        if name not in nodes:
            node = luna.Node(name = name, create = True, group = group)

            node.set('localboot', localboot)
            node.set('service', service)
            node.set('setupbmc', setupbmc)
            if port:
                node.set('port', port)
            if switch:
                node.set_switch( switch)
            if mac:
                node.set_mac(mac)

            return False, True, str(node)
#    except Exception as e:
#        return True, False, str(e)

def luna_node_absent(data):
    locals().update(data)
    nodes = luna.list('node')
    try:
        if name not in nodes:
            return False, False, name
        else:
            node = luna.Node(name)
            node.delete()
            return False, True, name
    except Exception as e:
        return True, False, str(e)

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name          = dict(type="str", required=True),
            group         = dict(type="str", required=True),
            comment       = dict(type="str", default="", required=False),
            interfaces    = dict(type="list", default=[], required=False),
            localboot     = dict(type="bool", default=False, required=False),
            setupbmc      = dict(type="bool", default=True, required=False),
            service       = dict(type="bool", default=False, required=False),
            mac           = dict(type="str", default="",required=False),
            switch        = dict(type="str",  default="",required=False),
            port          = dict(type="int",  default=0,required=False),
            state         = dict(type="str", default="present",
                                             choices=['present', 'absent'] )
            )
    )
    
    choice_map = {
        "present": luna_node_present,
        "absent": luna_node_absent,
    }

    is_error, has_changed, result = choice_map.get(
        module.params['state'])(module.params)

    if not is_error:
        module.exit_json(changed=has_changed, meta=result)
    else:
        module.fail_json(msg="Error node changing", meta=result)
    

if __name__ == '__main__':  
    main()
