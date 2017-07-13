#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pycompat24 import get_exception
import json
import luna
import sys

def luna_group_present(data):
        name = data['name']
        groups = luna.list('group')
        data.pop('state')
       
    #try:
        msg=""
        if name not in groups:
            interfaces = data['interfaces']
            data.pop('interfaces')
            data['create'] = True
            data['interfaces'] = []
            for interface in interfaces:
                for k in interface.keys():
                    print k,interface[k]
                if len(interface['networks']) > 2:
                    return True, False, "Too much networks"
                nets = {}
                for network in interface['networks']:
                    net = luna.Network(network)
                    if net.version in nets:
                        return True, False, "The can be only one v4 and one v6 network"
                    nets[net.version] = net
                data['interfaces'].append(interface['name']) 

            group = luna.Group(**data)
            
            for interface in interfaces:
                for network in interface['networks']:
                    group.set_net_to_if(interface['name'], network)

            return False, True, str(group)
        else:
            group = luna.Group(name = name)
            changed = False
            ifnames = [i['name'] for i in data['interfaces']]
            for iface in group.list_ifs().keys():
                if iface not in ifnames:
                    changed = True
                    group.del_interface(iface)
            for key in data.keys():
                if key == "interfaces":
                   ifaces = group.list_ifs()
                   for interface in data["interfaces"]:
                       yaml_nets = {'4': None, '6': None }
                       #Sanity checks
                       if len(interface['networks']) > 2:
                           return True, False, "Too much networks"
                       nets = {}
                       for network in interface['networks']:
                           net = luna.Network(network)
                           if net.version in nets:
                               return True, False, "The can be only one v4 and one v6 network"
                           nets[net.version] = net

                       if interface['name'] in ifaces.keys():
                           if 'params' in interface.keys() and group.show_if(interface['name'])['options'] != interface['params']:
                               group.set_if_params(interface['name'],interface['params']) 
                               changed = True
                           iface = group.show_if(interface['name'])
                           group_nets = [ iface['network']['4']['name'], iface['network']['6']['name'] ]
                           ans_nets = ['','']
                           for network in interface['networks']:
                               if luna.Network(network).version ==4:
                                   ans_nets[0] = network
                               else:
                                   ans_nets[1] = network

                           for network in interface['networks']:
                               if network == '':
                                   continue
                               if luna.Network(network).version ==4:
                                   if network != group_nets[0]:
                                       group.set_net_to_if(interface['name'], network)
                                       changed = True
                               else:
                                   if network != group_nets[1]:
                                       group.set_net_to_if(interface['name'], network)
                                       changed = True
                               
                           for network in group_nets:
                               if network == '':
                                   continue
                               if luna.Network(network).version ==4:
                                   if network != ans_nets[0]:
                                       group.del_net_from_if(interface['name'], version='4')
                                       if ans_nets[0]!='':
                                           group.set_net_to_if(interface['name'], ans_nets[0])
                                       changed = True
                               else:
                                   if network != ans_nets[1]:
                                       msg +="Remove net"
                                       msg += str(interface['name']) + " version=6"
                                       group.del_net_from_if(interface['name'], version='6')
                                       if ans_nets[1]!='':
                                           group.set_net_to_if(interface['name'], ans_nets[1])
                                       changed = True
                       else:
                           msg+="Add interface" + str(ifaces)
                           group.add_interface(interface['name'])
                           for network in interface['networks']:
                               group.set_net_to_if(interface['name'], network)
                           if 'params' in interface.keys():
                               group.set_if_params(interface['name'],interface['params']) 
                          
                           changed = True

            data.pop('interfaces');
            if data[key]!= None and group.get(key) != data[key]:
                changed = True
                group.set(key, data[key])
 
            return False, changed, msg
    #except Exception as e:
    #    return True, False, str(e)

def luna_group_absent(data):
    group = luna.list('group')
    name = data['name']
    try:
        if name not in group:
            return False, False, name
        else:
            group = luna.Group(name)
            group.delete()
            return False, True, name
    except Exception as e:
        return True, False, str(e)

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name          = dict(type="str", required=True),
            osimage       = dict(type="str", required=False),
            bmcsetup      = dict(type="str", required=False),
            domain        = dict(type="str", default=None, required=False),
            interfaces    = dict(type="list", required=True),
            prescript     = dict(type="str", default="", requires=False),
            postscript    = dict(type="str", default="", requires=False),
            partscript    = dict(type="str", default="", requires=False),
            state         = dict(type="str", default="present",
                                             choices=['present', 'absent'] )
            )
    )
    
    choice_map = {
        "present": luna_group_present,
        "absent": luna_group_absent,
    }

    is_error, has_changed, result = choice_map.get(
        module.params['state'])(module.params)

    if not is_error:
        module.exit_json(changed=has_changed, meta=result)
    else:
        module.fail_json(msg="Error group changing", meta=result)
    

if __name__ == '__main__':  
    main()
