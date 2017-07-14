#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import luna


def luna_osimage_present(data):

    changed = False
    ret = True

    try:
        osimage = luna.OsImage(name=data['name'])
    except RuntimeError:
        osimage = luna.OsImage(
            name=data['name'],
            create=True,
            path=data['path'],
            kernver=data['kernver'],
            kernopts=data['kernopts'],
            comment=data['comment'])
        changed = True

    for key in ['path', 'kernver', 'kernopts',
                'dracutmodules', 'kernmodules', 'grab_exclude_list',
                'grab_filesystems']:
        if data[key] and data[key] != osimage.get(key):
            ret &= osimage.set(key, data[key])
            changed = True

    if data['comment'] != osimage.get(data['comment']):
        ret &= osimage.set('comment', data['comment'])
        changed = True

    if data['pack']:
        changed = True
        if data['copy_boot']:
            ret &= osimage.copy_boot()
        else:
            ret &= osimage.pack_boot()
        ret &= osimage.create_tarball()
        ret &= osimage.create_torrent()

    return not ret, changed, osimage.get('name')


def luna_osimage_absent(data):
    name = data['name']

    try:
        osimage = luna.OsImage(name)
    except RuntimeError:
        return False, False, name

    return not osimage.delete(), True, name


def main():
    module = AnsibleModule(
        argument_spec={
            'name': {
                'type': 'str', 'required': True},

            'path': {
                'type': 'str', 'required': False},

            'kernver': {
                'type': 'str', 'default': '', 'required': False},

            'kernopts': {
                'type': 'str', 'default': '', 'required': False},

            'comment': {
                'type': 'str', 'default': '', 'required': False},

            'dracutmodules': {
                'type': 'str', 'default': '', 'required': False},

            'kernmodules': {
                'type': 'str', 'default': '', 'required': False},

            'grab_exclude_list': {
                'type': 'str', 'default': '', 'required': False},

            'grab_filesystems': {
                'type': 'str', 'default': '', 'required': False},

            'pack': {
                'type': 'bool', 'default': False, 'required': False},

            'copy_boot': {
                'type': 'bool', 'default': False, 'required': False},

            'state': {
                'type': 'str', 'default': 'present',
                'choices': ['present', 'absent']}
        }
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
