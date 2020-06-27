# cluegen.py
#
# Classes generated from type clues.
#
#     https://github.com/dabeaz/cluegen
#
# Author: David Beazley (@dabeaz).
#         http://www.dabeaz.com
#
# Copyright (C) 2018-2020.
#
# Permission is granted to use, copy, and modify this code in any
# manner as long as this copyright message and disclaimer remain in
# the source code.  There is no warranty.  Try to use the code for the
# greater good.

import types

from functools import lru_cache, wraps

__all__ = 'all_clues', 'cluegen', 'Datum', 'FrozenDatum'


@lru_cache(maxsize=32)
def all_clues(cls):
    """collect all type clues from a class and base classes"""
    clues = {}
    for c in reversed(cls.__mro__):
        clues.update(getattr(c, '__annotations__', {}))
    return clues


def cluegen(func):
    """decorator to define methods of a class as a code generator"""

    def __get__(self, instance, cls):
        locs = {}
        code = func(cls) + '\n    pass'
        exec(code, locs)
        meth = wraps(func)(locs[func.__name__])
        setattr(cls, func.__name__, meth)
        return meth.__get__(instance, cls)

    def __set_name__(self, cls, name):
        methods = cls.__dict__.get('_methods', list(cls._methods))
        if '_methods' not in cls.__dict__:
            cls._methods = methods
        cls._methods.append((name, self))

    return type(f'ClueGen_{func.__name__}', (), dict(__get__=__get__,
                                                     __set_name__=__set_name__))()


class DatumBase:
    """base class for defining data structures"""
    __slots__ = ()
    _methods = []

    @classmethod
    def __init_subclass__(cls):
        submethods = []
        for name, val in cls._methods:
            if name not in cls.__dict__:
                setattr(cls, name, val)
                submethods.append((name, val))
            elif val is cls.__dict__[name]:
                submethods.append((name, val))

        if submethods != cls._methods:
            cls._methods = submethods


class Datum(DatumBase):
    __slots__ = ()

    @cluegen
    def __init__(cls):
        clues = all_clues(cls)
        args = cls._gen_init_args(clues)
        body = cls._gen_init_body(clues)
        return f'def __init__(self, {args}):\n{body}\n'

    @classmethod
    def _gen_init_args(cls, clues):
        return ', '.join(f'{name}={getattr(cls, name)!r}'
                         if hasattr(cls, name) and not isinstance(getattr(cls, name),
                                                                  types.MemberDescriptorType)
                         else name
                         for name in clues)

    @classmethod
    def _gen_init_body(cls, clues, prepend=''):
        return '\n'.join(f'    self.{prepend}{name} = {name}' for name in clues)

    @cluegen
    def __repr__(cls):
        clues = all_clues(cls)
        fmt = ', '.join('%s={self.%s!r}' % (name, name) for name in clues)
        return 'def __repr__(self):\n' \
               '    return f"{type(self).__name__}(%s)"' % fmt

    @cluegen
    def __iter__(cls):
        clues = all_clues(cls)
        values = '\n'.join(f'   yield self.{name}' for name in clues)
        return 'def __iter__(self):\n' + values

    @cluegen
    def __eq__(cls):
        clues = all_clues(cls)
        selfvals = ','.join(f'self.{name}' for name in clues) or None
        othervals = ','.join(f'other.{name}' for name in clues) or None
        return 'def __eq__(self, other):\n' \
               '    if self.__class__ is other.__class__:\n' \
               f'        return ({selfvals},) == ({othervals},)\n' \
               '    else:\n' \
               '        return NotImplemented\n'

    @cluegen
    def __getitem__(cls):
        return '\n'.join(('def __getitem__(self, item):',
                          f'    return getattr(self, {tuple(all_clues(cls))}[item])'))

    @cluegen
    def __len__(cls):
        length = len(all_clues(cls))
        return '\n'.join(('def __len__(self):',
                          f'    return {length}'))


def _frozen_error(self, *_):
    raise AttributeError(f"can't set/del attr on FrozenDatum type {type(self).__name__!r}")


class FrozenMeta(type):
    _cluegen_prop_store_prefix_ = '_cluegen_prop_'
    _cluegen_defaults_ = {}

    def __new__(mcs, name, bases, cls_dict):
        defaults = {}
        for n in cls_dict.get('__annotations__', {}):
            if n in cls_dict:  # means a default value is set (e.g. a: int = 4)
                defaults[n] = cls_dict[n]
            cls_dict[n] = property(
                lambda self, prop_name=f'{mcs._cluegen_prop_store_prefix_}{n}': getattr(self, prop_name),
                _frozen_error,
                _frozen_error
            )
        res = super().__new__(mcs, name, bases, cls_dict)
        mcs._cluegen_defaults_[res] = defaults
        return res

    @classmethod
    def get_defaults(mcs, cls):
        res = {}
        for c in cls.__mro__:
            res.update(mcs._cluegen_defaults_.get(c, {}))
        return res


class FrozenDatum(Datum, metaclass=FrozenMeta):

    @classmethod
    def _gen_init_args(cls, clues):
        defaults = FrozenMeta.get_defaults(cls)
        defaults = {k: f'{k}={v}' for k, v in defaults.items()}
        return ', '.join(defaults.get(c, c) for c in clues)

    @classmethod
    def _gen_init_body(cls, clues, prepend=FrozenMeta._cluegen_prop_store_prefix_):
        return super()._gen_init_body(clues, prepend)

    @cluegen
    def __hash__(cls):
        clues = all_clues(cls)
        if clues:
            self_tuple = '(' + ','.join(f'self.{name}' for name in clues) + ',)'
        else:
            self_tuple = '()'
        return 'def __hash__(self):\n' \
               f'    return hash({self_tuple})\n'


if __name__ == '__main__':
    # example
    class Coordinates(FrozenDatum):
        x: int
        y: int


    crds = Coordinates(2, 3)
    print(crds)
