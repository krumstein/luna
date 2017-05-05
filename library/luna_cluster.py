#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pycompat24 import get_exception
import json
import luna
import sys
import traceback

def luna_cluster_present(data):
    #for k, v in data.items():
    #     exec('%s = v' % k)
    data.pop('state')
    try:
        cluster = luna.Cluster()
    except RuntimeError:
        init = { key: data[key] for key in data if key in ['nodeprefix' , 'nodedigits' , 'path' , 'user'] }
        init['create'] = True
        cluster = luna.Cluster(**init)
        return False, True, str(cluster)

    try:
        if data['makedhcp'] == True:
        elif data['makedns'] == True:
          
        else:
            cluster = luna.Cluster()
            changed = False
            out = ""
            for key in data:
                if data[key]!= None and cluster.get(key) != data[key]:
                    out += "{}={},".format(key,data[key])
                    changed = True
                    cluster.set(key, data[key])   
            return False, changed, str(cluster) + out
    except Exception as e:
        return True, False, str(e) + traceback.format_exc()

#    try:
#        if name not in clusters:
#            data['create'] = True
#            cluster = luna.BMCSetup(**data)
#            return False, True, str(cluster)
#        else:
#            cluster = luna.BMCSetup(name = name)
#            changed = False
#            for key in data:
#                if data[key]!= None and cluster.get(key) != data[key]:
#                    changed = True
#                    cluster.set(key, data[key])   
#            return False, changed, str(cluster)
#    except Exception as e:
#        return True, False, str(e) + traceback.format_exc()
#
def luna_cluster_absent(data):
    for k, v in data.items():
         exec('%s = v' % k)
    try:
        cluster = luna.Cluster()
        cluster.delete()
        return False, True, ""
    except Exception as e:
        return True, False, str(e)+ traceback.format_exc()



def main():
    module = AnsibleModule(
        argument_spec = dict(
            nodeprefix               = dict(type="str",  default="node",   required=False),
            nodedigits               = dict(type="str",  default="3",      required=False),
            user                     = dict(type="str",  default="luna",   required=False),
            path                     = dict(type="str",  default=None,     required=False),
            frontend_address         = dict(type="str",  default=None,     required=False),
            frontend_port            = dict(type="int",  default=None,     required=False),
            server_port              = dict(type="int",  default=None,     required=False),
            tracker_interval         = dict(type="int",  default=None,     required=False),
            tracker_min_interval     = dict(type="int",  default=None,     required=False),
            tracker_maxpeers         = dict(type="int",  default=None,     required=False),
            torrent_listen_port_min  = dict(type="int",  default=None,     required=False),
            torrent_listen_port_max  = dict(type="int",  default=None,     required=False),
            torrent_pidfile          = dict(type="str",  default=None,     required=False),
            lweb_num_proc            = dict(type="int",  default=None,     required=False),
            lweb_pidfile             = dict(type="str",  default=None,     required=False),
            cluster_ips              = dict(type="str",  default=None,     required=False),
            named_include_file       = dict(type="str",  default=None,     required=False),
            named_zone_dir           = dict(type="str",  default=None,     required=False),
            
            makedhcp                 = dict(type="bool", default=False,    required=False),
            no_ha                    = dict(type="bool", default=True,     required=False),
            network                  = dict(type="str",  default=None,     required=False),
            start_ip                 = dict(type="str",  default=None,     required=False),
            end_ip                   = dict(type="str",  default=None,     required=False),

            makedns                  = dict(type="bool", default=False,    required=False),

            state                    = dict(type="str",  default="present",
                                                         choices=["present", "absent"] )
            )
    )
    
    choice_map = {
        "present": luna_cluster_present,
        "absent": luna_cluster_absent,
    }

    is_error, has_changed, result = choice_map.get(
        module.params['state'])(module.params)

    if not is_error:
        module.exit_json(changed=has_changed, meta=result)
    else:
        module.fail_json(msg="Error osimage changing", meta=result)
    

if __name__ == '__main__':  
    main()
