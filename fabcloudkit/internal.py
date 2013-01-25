from __future__ import absolute_import

# pypi
from fabric.colors import *


class HaltError(StandardError):
    def __init__(self, msg, *args, **kwargs):
        super(HaltError,self).__init__(*((msg,)+args), **kwargs)
        self.msg = msg

def message(text):
    white_msg(text)

def white_msg(text, bold=False):
    print(white(text, bold))

def green_msg(text, bold=False):
    print(green(text, bold))

def red_msg(text, bold=False):
    print(red(text, bold))

def yellow_msg(text, bold=False):
    print(yellow(text, bold))

def start_msg(text):
    white_msg(text, True)

def succeed_msg(text):
    green_msg(text)

def failed_msg(text):
    red_msg(text, True)
