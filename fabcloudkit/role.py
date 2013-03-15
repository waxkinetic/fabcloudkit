"""
    fabcloudkit

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# standard
import time

# pypi
from boto.ec2 import EC2Connection
from fabric.context_managers import settings
from fabric.network import disconnect_all
import yaml

# package
from fabcloudkit import cfg, ctx
from .activator import Activator
from .builder import Builder
from .dotdict import dotdict
from .provisioner import Provisioner


class Role(dotdict):
    def __init__(self, path=None):
        super(Role,self).__init__()
        if path:
            self.load(path)

    def activate_instance(self, inst, force=False):
        # this seems to mitigate random SSH connection issues.
        disconnect_all()

        activator = Activator(self)
        with settings(host_string=inst.public_dns_name, user=self.user):
            build_name, port = activator.execute(force)
            if build_name is not None:
                inst.add_tag(cfg().fck_active_build, '{build_name} ({port})'.format(**locals()))

    def deactivate_instance(self, inst):
        activator = Activator(self)
        with settings(host_string=inst.public_dns_name, user=self.user):
            activator.deactivate()
            inst.remove_tag(cfg().fck_active_build)

    def build_instance(self, inst):
        # this seems to mitigate random SSH connection issues.
        disconnect_all()

        builder = Builder(self)
        with settings(host_string=inst.public_dns_name, user=self.user):
            build_name = builder.execute()
            inst.add_tag(cfg().fck_last_good_build, build_name)

    def create_instance(self, image_id=None, key_name=None, instance_type=None, security_groups=None, **kwargs):
        # default to values specified in the role definition, but allow to be overridden.
        if image_id is None:
            image_id = self.aws.ami_id
        if key_name is None:
            key_name = self.aws.key_name
        if security_groups is None:
            security_groups = self.aws.security_groups
        if instance_type is None:
            instance_type = self.aws.instance_type

        # create the instance.
        conn = EC2Connection(ctx().aws_key, ctx().aws_secret)
        result = conn.run_instances(image_id, key_name=key_name,
            security_groups=security_groups, instance_type=instance_type, **kwargs)

        # wait until it's running.
        inst = result.instances[0]
        while inst.state != 'running':
            time.sleep(5)
            inst.update()
        return self.init_instance(inst)

    def init_instance(self, inst):
        inst.add_tag(cfg().fck_role, self.name)
        ctx().add_instance(inst)
        return inst

    def provision_instance(self, inst):
        # this seems to cure random SSH connection issues.
        disconnect_all()

        provisioner = Provisioner(self)
        with settings(host_string=inst.public_dns_name, user=self.user):
            provisioner.execute()

    def allows_access_to(self, role_name):
        allow_list = self.get('provision', {}).get('allow_access', {}).get('roles', [])
        if isinstance(allow_list, basestring):
            allow_list = [allow_list]
        return role_name in allow_list

    def load(self, path):
        with open(path, 'r') as f:
            self._set_dct(yaml.safe_load(f.read()))
