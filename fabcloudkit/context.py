"""
    fabcloudkit

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# standard
import os
import posixpath

# pypi
import boto.ec2
from fabric.api import env
import yaml

# package
from fabcloudkit import cfg
from .dotdict import dotdict
from .role import Role


class Context(dotdict):
    _contexts = []

    @classmethod
    def current(cls):
        return cls._contexts[0] if cls._contexts else None

    def __init__(self, file_path=None, is_current=True):
        super(Context,self).__init__()
        self._real_prop('_roles', [])
        self._real_prop('_instances', {})

        if file_path:
            self.load(file_path)
        if is_current:
            self.set_current(True)

    def add_instance(self, inst):
        self._instances[inst.public_dns_name] = inst

    def aws_sync(self):
        conn = boto.ec2.EC2Connection(Context.current().aws_key, Context.current().aws_secret)
        result = conn.get_all_instances()

        self._instances = []
        for reservation in result:
            for instance in reservation.instances:
                if instance.state not in ('terminated', 'shutting-down'):
                    self.add_instance(instance)

    def get_host_in_role(self, role_name):
        for inst in self._instances.itervalues():
            instance_role_name = inst.tags.get(cfg().fck_role, None)
            if instance_role_name == role_name:
                return inst, self.get_role(role_name)
        raise RuntimeError('No instance in role "{0}" is available.'.format(role_name))

    def all_hosts_in_role(self, role_name):
        hosts = []
        for inst in self._instances.itervalues():
            if role_name == inst.tags.get(cfg().fck_role, None):
                hosts.append(inst)
        return hosts, self.get_role(role_name)

    def builds_root(self):
        return posixpath.join(cfg().deploy_root, self.name, cfg().builds_dir)

    def build_path(self, file_or_dir_name):
        return posixpath.join(self.builds_root(), file_or_dir_name)

    def repos_root(self):
        return posixpath.join(cfg().deploy_root, self.name, cfg().repos_dir)

    def repo_path(self, file_or_dir_name):
        return posixpath.join(self.repos_root(), file_or_dir_name)

    def get_key(self, name):
        key = self.get('keys', {}).get(name, None)
        if not key:
            raise RuntimeError('Key "{0}" is not defined.'.format(name))
        return key

    def keys(self):
        return [self.get_key(name) for name in self.get('keys', {}).keys()]

    def load(self, file_path):
        with open(file_path, 'r') as f:
            # note: calling safe_load() disables the "!env" extension tag.
            self._set_dct(yaml.load(f))

        # load roles.
        dir = os.path.dirname(file_path)
        del self._roles[:]
        for file_name in self.get('roles', []):
            self._roles.append(Role(os.path.join(dir, file_name)))

    def get_role(self, name):
        for role in self._roles:
            if role.name == name:
                return role
        raise RuntimeError('No role available named "{0}"'.format(name))

    def roles(self):
        # return a copy of the roles list.
        return list(self._roles)

    def get_repo(self, name):
        repo = self.get('repos', {}).get(name, None)
        if not repo:
            raise RuntimeError('Repo "{0}" is not defined.'.format(name))

        # if no explicit dir or dir is None, extract it from the url.
        if not repo.get('dir', None):
            repo.dir = repo.url.rsplit('/', 1)[1].rsplit('.')[0]

        # if no explicit package_name is given, default to the dir.
        if not repo.get('package_name', None):
            repo.package_name = repo.dir

        return repo

    def repos(self):
        return [self.get_repo(name) for name in self.get('repos', {}).keys()]

    def set_current(self, is_current=True):
        changed = False
        if not is_current and self.current() is self:
            # pop ourselves off the context stack.
            self._contexts.pop(0)
            changed = True
        elif is_current:
            # push ourselves onto the top of the context stack.
            self._contexts.insert(0, self)
            changed = True

        if changed:
            # configure the fabric environment for this context.
            ctx = self.current()
            env.key_filename = ctx.key_filename if ctx else ''
            env.warn_only = True
