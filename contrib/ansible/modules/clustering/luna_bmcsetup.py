#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import luna


def luna_bmcsetup_present(data):
    data.pop('state')
    name = data.pop('name')
    changed = False
    ret = True

    try:
        bmcsetup = luna.BMCSetup(name=name)
    except RuntimeError:
        args = {}
        for key in data:
            if data[key] is not None:
                args[key] = data[key]
        args['name']=name
        args['create']=True
        bmcsetup = luna.BMCSetup(**args)
        changed = True

    for key in data:
        if data[key] is not None and bmcsetup.get(key) != data[key]:
            changed = True
            ret &= bmcsetup.set(key, data[key])

    return not ret, changed, str(bmcsetup)


def luna_bmcsetup_absent(data):
    name = data['name']
    try:
        bmcsetup = luna.BMCSetup(name=name)
    except RuntimeError:
        return False, False, name

    return not bmcsetup.delete(), True, name


def main():
    module = AnsibleModule(
        argument_spec={
            'name': {
                'type': 'str', 'required': True},
            'user': {
                'type': 'str', 'required': False},
            'password': {
                'type': 'str', 'default': None, 'required': False},
            'mgmtchannel': {
                'type': 'int', 'default': None, 'required': False},
            'netchannel': {
                'type': 'int', 'default': None, 'required': False},
            'userid': {
                'type': 'int', 'default': None, 'required': False},
            'comment': {
                'type': 'str', 'default': None, 'required': False},
            'state': {
                'type': 'str', 'default': 'present',
                'choices': ['present', 'absent']}
        }
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
        module.fail_json(msg="Error bmcsetup changing", meta=result)


if __name__ == '__main__':
    main()
