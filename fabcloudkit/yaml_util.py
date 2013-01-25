from __future__ import absolute_import

import os
import yaml


def env_constructor(loader, node):
    name = loader.construct_scalar(node)
    return os.environ[name]

# this tag only works if using yaml.load(), not yaml.safe_load().
yaml.add_constructor(u'!env', env_constructor)
