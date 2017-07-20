#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import luna


def luna_otherdev_present(data):
    data.pop('state')
    name = data.pop('name')
    changed = False
    ret = True

    try:
        otherdev = luna.OtherDev(name=name)
    except RuntimeError:
        if not data['connected']:
            err_msg = ("Need to specify at least one IP and network " +
                       "device is connected to")
            return True, changed, err_msg

        if 'network' not in data['connected'][0]:
            err_msg = ("Network to which device is connected " +
                       "needs to be specified")
            return True, changed, err_msg

        if 'ip' not in data['connected'][0]:
            err_msg = ("IP device is reachable " +
                       "needs to be specified")
            return True, changed, err_msg

        args = {
            'name': name,
            'create': True,
            'network': data['connected'][0]['network'],
            'ip': data['connected'][0]['ip'],
        }
        otherdev = luna.OtherDev(**args)
        changed = True

    if (data['comment'] is not None
            and data['comment'] != otherdev.get('comment')):
        otherdev.set('comment', data['comment'])
        changed = True

    ansible_nets = {}
    for elem in data['connected']:
        if elem['network'] in ansible_nets:
            err_msg = ('Network {} specified multiple times'
                       .format(elem[elem['network']]))
            return True, changed, err_msg

        ansible_nets[elem['network']] = elem['ip']

    configured_nets = otherdev.list_nets()

    del_nets = [n for n in configured_nets if n not in ansible_nets]

    for net in del_nets:
        ret &= otherdev.del_net(net)
        changed = True

    for net in ansible_nets:
        ip = ansible_nets[net]
        if otherdev.get_ip(net) != ip:
            ret &= otherdev.set_ip(net, ip)
            changed = True

    return not ret, changed, str(otherdev)


def luna_otherdev_absent(data):
    name = data['name']
    try:
        otherdev = luna.OtherDev(name=name)
    except RuntimeError:
        return False, False, name

    return not otherdev.delete(), True, name


def main():
    module = AnsibleModule(
        argument_spec={
            'name': {
                'type': 'str', 'required': True},
            'connected': {
                'type': 'list', 'default': None, 'required': False},
            'comment': {
                'type': 'str', 'default': None, 'required': False},
            'state': {
                'type': 'str', 'default': 'present',
                'choices': ['present', 'absent']}
        }
    )

    choice_map = {
        "present": luna_otherdev_present,
        "absent": luna_otherdev_absent,
    }

    is_error, has_changed, result = choice_map.get(
        module.params['state'])(module.params)

    if not is_error:
        module.exit_json(changed=has_changed, meta=result)
    else:
        module.fail_json(msg="Error otherdev changing", meta=result)


if __name__ == '__main__':
    main()
