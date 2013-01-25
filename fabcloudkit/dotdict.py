from __future__ import absolute_import


class dotdict(object):
    def __init__(self, dct=None):
        object.__setattr__(self, '_dct', dct if dct else {})

    def __contains__(self, key):
        return self._dct.__contains__(key)

    def __getattr__(self, k):
        val = self._dct[k]
        return self._fixup(k, val)

    def __setattr__(self, k, v):
        self._dct[k] = v

    def __getitem__(self, key):
        val = self._dct.__getitem__(key)
        return self._fixup(key, val)

    def __iter__(self):
        return self._dct.__iter__()

    def __setitem__(self, key, value):
        return self._dct.__setitem__(key, value)

    def __delitem__(self, key):
        return self._dct.__delitem__(key)

    def __repr__(self):
        return '<{0} in {1}: {2}>'.format(
            self.__class__.__name__, self.__module__, self._dct.__repr__())

    def __reversed__(self):
        return self._dct.__reversed__()

    def get(self, name, default=None):
        val = self._dct.get(name, default)
        return self._fixup(name, val)

    def iteritems(self):
        return self._dct.iteritems()

    def iterkeys(self):
        return self._dct.iterkeys()

    def itervalues(self):
        return self._dct.itervalues()

    def items(self):
        return self._dct.items()

    def keys(self):
        return self._dct.keys()

    def values(self):
        return self._dct.values()

    def _set_dct(self, dct):
        object.__setattr__(self, '_dct', dct)

    def _real_prop(self, k, v):
        object.__setattr__(self, k, v)

    def _fixup(self, k, v):
        if isinstance(v, dict):
            v = dotdict(v)
            self._dct[k] = v
        return v

