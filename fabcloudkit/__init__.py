"""
    fabcloudkit

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

__version__ = '0.01-dev'

# access to the current Context without having to import the context module.
def ctx():
    return Context.current()

# access to the current Config without having to import the config module.
def cfg():
    return Config.inst()

from .util import *
from .yaml_util import *

from .config import *
from .context import *
from .role import *
from .toolbase import *

def load(self, path):
    with open(path, 'r') as f:
        self._set_dct(yaml.safe_load(f.read()))

import fabcloudkit.activation_tools
import fabcloudkit.build_tools
import fabcloudkit.tool
