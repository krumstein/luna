#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pycompat24 import get_exception
import json
import luna
import sys
import traceback

def luna_bmcsetup_present(data):
    for k, v in data.items():
         exec('%s = v' % k)
    bmcsetups = luna.list('bmcsetup')
    data.pop('state')
    try:
        if name not in bmcsetups:
            data['create'] = True
            bmcsetup = luna.BMCSetup(**data)
            return False, True, str(bmcsetup)
        else:
            bmcsetup = luna.BMCSetup(name = name)
            changed = False
            for key in data:
                if data[key]!= None and bmcsetup.get(key) != data[key]:
                    changed = True
                    bmcsetup.set(key, data[key])   
            return False, changed, str(bmcsetup)
    except Exception as e:
        return True, False, str(e) + traceback.format_exc()

def luna_bmcsetup_absent(data):
    for k, v in data.items():
         exec('%s = v' % k)
    bmcsetup = luna.list('bmcsetup')
    try:
        if name not in bmcsetup:
            return False, False, name
        else:
            bmcsetup = luna.BMCSetup(name = name)
            bmcsetup.delete()
            return False, True, name
    except Exception as e:
        return True, False, str(e)+ traceback.format_exc()



def main():
    module = AnsibleModule(
        argument_spec = dict(
            name          = dict(type="str", required=True),
            user          = dict(type="str", required=False),
            password      = dict(type="str", default=None, required=False),
            mgmtchannel   = dict(type="int", default=None, required=False),
            netchannel    = dict(type="int", default=None, required=False),
            userid        = dict(type="int", default=None, required=False),
            state         = dict(type="str", default="present",
                                             choices=['present', 'absent'] )
            )
    )
    
    choice_map = {
        "present": luna_bmcsetup_present,
        "absent": luna_bmcsetup_absent,
    }

    is_error, has_changed, result = choice_map.get(
        module.params['state'])(module.params)

    if not is_error:
        module.exit_json(changed=has_changed, meta=result)
    else:
        module.fail_json(msg="Error osimage changing", meta=result)
    

if __name__ == '__main__':  
    main()
