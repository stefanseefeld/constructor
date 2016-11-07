#
# Copyright (c) 2016 Stefan Seefeld
# All rights reserved.
#
# This file is part of Faber. It is made available under the
# Boost Software License, Version 1.0.
# (Consult LICENSE or http://www.boost.org/LICENSE_1_0.txt)

from . import types
from .feature import feature, set
from os.path import normpath, join
from collections import defaultdict
import string

intermediate= 0x0001
nocare=       0x0002
notfile=      0x0004
always=       0x0008
leaves=       0x0010
noupdate=     0x0020
rmold=        0x0080
xfail=        0x0100
isfile=       0x0400
precious=     0x0800

_type = type

class path_formatter(string.Formatter):

    def format_field(self, value, spec):
        """Remove path segments corresponding to undefined features."""
        if value == None:
            return '.'
        else:
            return super(path_formatter, self).format_field(value, spec)
    def get_value(self, key, args, kwargs):
        """Remove path segments corresponding to non-existent features."""
        try:
            if isinstance(key, int):
                return args[key]
            else:
                return kwargs[key]
        except KeyError:
            return '.'

class artefact(object):
    """An artefact can be generated by a build."""

    # reverse lookup: finding an artefact from its bound name...
    _bnames = {}
    # ...and its qname. (Note that multiple artefact may use the
    # same qname (if they have different features).
    _qnames = defaultdict(list)

    def register(self):
        artefact._bnames[self.bound_name] = self
        artefact._qnames[self.qname].append(self)

    @staticmethod
    def iter():
        """Iterate over all registered artefacts."""

        # iterate grouped by qname
        return iter(a for qname in artefact._qnames.values() for a in qname)

    @staticmethod
    def lookup(qname):
        """Find an artefact by (qualified) name."""

        if qname not in artefact._qnames:
            raise KeyError(qname)
        else:
            return artefact._qnames[qname]

    def __init__(self, name, sources=None, attrs=0,
                 features=(), path_spec='', use=(),
                 type=None):
        self.type = type
        type = _type # restore the original
        # for convenience, accept 'sources' to be a list or a single string
        sources = sources if type(sources) is list else [sources]
        # for convenience, accept a single value in 'features'
        if not isinstance(features, set):
            features = set(features)
        if not isinstance(use, set):
            use = set(use)

        self.name = name
        # import here to avoid circular dependency
        from .module import module
        self.module = module.current
        self.qname = self.module.qname(self.name)        
        self.sources = sources
        self.attrs = attrs
        self.path_spec = path_spec
        self.features = self.module.features.copy()
        self.features.update(features)
        # merge 'usage' features from sources
        for s in self.sources:
            if isinstance(s, artefact) and s.use:
                self.features += s.use
        self.use = use
        self.expand()

    @property
    def bound_name(self):
        return self.qname if self.attrs & notfile else self.filename

    def __call__(self, features):
        """Clone this artefact, but apply new features."""

        if not isinstance(features, set):
            features = set(features)
        import copy
        clone = copy.copy(self)
        clone.features = self.module.features
        clone.features.update(features)
        clone.expand()
        return clone

    def expand(self):
        if not self.attrs & notfile and not self.type:
            self.type = types.type.discover(self.filename)

    def _update(self, features, path_spec):
        self.features.update(features)
        self.path_spec = path_spec

    @property
    def filename(self):
        return join(self.module.builddir, self.relpath, self.name)

    @property
    def relpath(self):
        f = path_formatter()
        return normpath(f.format(self.path_spec, **self.features._features))

    def __repr__(self):
        return '<artefact {}>'.format(self.name)
