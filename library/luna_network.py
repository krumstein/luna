#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pycompat24 import get_exception
import json
import luna
import sys

def luna_network_present(data):
        name = data['name']
        network = data['network']
        prefix = data['prefix']
        ns_hostname = data['ns_hostname']
        ns_ip = data['ns_ip']
        comment = data['comment']
        networks = luna.list('network')
        msg = ""
    #    try:
        if name not in networks:
            net = luna.Network(name = name, create = True, NETWORK = network, PREFIX = prefix, ns_hostname = ns_hostname, ns_ip = ns_ip)
            return False, True, str(net)
        else:
            net = luna.Network(name = name)
            changed = False
            version = luna.utils.ip.get_ip_version(network)
 
            if luna.utils.ip.ntoa(luna.utils.ip.get_num_subnet(network, prefix, version),version) != net.get('NETWORK'):
                changed = True
                net.set('NETWORK', network)
            if prefix != net.get('PREFIX'):
                changed = True
                net.delete()
                net = luna.Network(name = name, create = True, NETWORK = network, PREFIX = prefix, ns_hostname = ns_hostname, ns_ip = ns_ip)
            if ns_hostname and (ns_hostname != net.get('ns_hostname')):
                changed=True
                net.set('ns_hostname', ns_hostname)
            if ns_ip and (ns_ip != net.get('ns_ip')):
                changed = True
                net.set('ns_ip',ns_ip)
            if comment != net.get('comment'):
                changed = True
                net.set('comment',comment)
            return False, changed, msg+str(net)
#    except Exception as e:
#        return True, False, str(e)

def luna_network_absent(data):
    locals().update(data)
    for k, v in data.items():
         exec('%s = v' % k)
    networks = luna.list('network')
    try:
        if name not in networks:
            return False, False, name
        else:
            net = luna.Network(name)
            net.delete()
            return False, True, name
    except Exception as e:
        return True, False, str(e)

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name          = dict(type="str", required=True),
            network       = dict(type="str", required=False),
            prefix        = dict(type="int", required=False),
            ns_hostname   = dict(type="str", default=None, required=False),
            ns_ip         = dict(type="str", default=None, required=False),
            comment       = dict(type="str", default="", required=False),
            state         = dict(type="str", default="present",
                                             choices=['present', 'absent'] )
            )
    )
    
    choice_map = {
        "present": luna_network_present,
        "absent": luna_network_absent,
    }

    is_error, has_changed, result = choice_map.get(
        module.params['state'])(module.params)

    if not is_error:
        module.exit_json(changed=has_changed, meta=result)
    else:
        module.fail_json(msg="Error network changing", meta=result)
    

if __name__ == '__main__':  
    main()
