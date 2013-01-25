"""

Configuration settings are:

deploy_root:
    Specifies the root directory for deployed sites.
    Default: "/opt/www"

builds_dir:
    Name of the directory under <deploy_root> that contains builds.
    Default: "builds"

repos_dir:
    Name of the directory under <deploy_root> that contains cloned repositories.
    Default: "repos"

supervisord_include_conf:
    Specifies the root directory for site-specific conf files. These files contain only a [program]
    definition for a site, and are usually named in a build-specific way.
    Default: "/etc/supervisor/conf.d"

nginx_include_conf:
    Specifies the directory for site-specific Nginx config files. This files typically contain a
    single "server" definition.
    Default: "/etc/nginx/conf.d"

tools:
    Contains tool definitions.

"""
from __future__ import absolute_import

# standard
import os

# pypi
import yaml

# package
from .dotdict import dotdict


class Config(dotdict):
    _inst = None
    _loaded = False

    @classmethod
    def inst(cls):
        return cls._inst

    @classmethod
    def create(cls):
        if not cls._inst:
            cls._inst = Config()
        return cls._inst

    @classmethod
    def load(cls, path=None):
        cls.create().load_file(path)

    def __init__(self):
        if self._inst:
            raise RuntimeError('Attempt to create a second Config instance.')
        super(Config,self).__init__()
        self._inst = self

    def load_file(self, path=None):
        if not self._loaded:
            if path is None:
                path = os.path.join(os.getcwd(), 'fabcloudkit.yaml')
            with open(path, 'r') as f:
                self._set_dct(yaml.safe_load(f.read()))
        self._loaded = True

    def machine_key_file(self):
        return '~/.ssh/{0}'.format(self.fck_machine_key)

    def tool_info(self, name):
        tools = self.get('tools', None)
        if not tools:
            raise RuntimeError('No "tools" section in configuration.')
        info = tools.get(name, None)
        if not info:
            raise RuntimeError('Information for tool "{0}" not found.'.format(name))
        return info


Config.create()
