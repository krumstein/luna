#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pycompat24 import get_exception
import json
import luna
import sys
import traceback

def luna_osimage_present(data):
    for k, v in data.items():
         exec('%s = v' % k)
    osimages = luna.list('osimage')
    try:
        if name not in osimages:
            if path in [ luna.OsImage(o).get('path') for o in luna.list('osimage')  ]:
                return True,False,"This path already exists in osimages"    
            osimage = luna.OsImage(name = name, create = True,  path = path, kernver = kernver, kernopts = kernopts)
            return False, True, str(osimage)
        else:
            osimage = luna.OsImage(name = name)
            changed = False
            if path != osimage.get('path'):
                changed = True
                osimage.set('path',path)
            if kernver != osimage.get('kernver'):
                changed = True
                osimage.set('kernver',kernver)
            if kernopts != osimage.get('kernopts'):
                changed = True
                osimage.set('kernopts',kernopts)
            return False, changed, str(osimage.get('kernopts'))
    except Exception as e:
        return True, False, str(e) + traceback.format_exc()

def luna_osimage_absent(data):
    locals().update(data)
    for k, v in data.items():
         exec('%s = v' % k)
    osimages = luna.list('osimage')
    try:
        if name not in osimages:
            return False, False, name
        else:
            osimage = luna.OsImage(name = name)
            osimage.delete()
            return False, True, name
    except Exception as e:
        return True, False, str(e)


def main():
    module = AnsibleModule(
        argument_spec = dict(
            name          = dict(type="str", required=True),
            path          = dict(type="str", required=False),
            kernver       = dict(type="str", default='ANY', required=False),
            kernopts      = dict(type="str", default='', required=False),
            state         = dict(type="str", default="present",
                                             choices=['present', 'absent'] )
            )
    )
    
    choice_map = {
        "present": luna_osimage_present,
        "absent": luna_osimage_absent,
    }

    is_error, has_changed, result = choice_map.get(
        module.params['state'])(module.params)

    if not is_error:
        module.exit_json(changed=has_changed, meta=result)
    else:
        module.fail_json(msg="Error osimage changing", meta=result)
    

if __name__ == '__main__':  
    main()
