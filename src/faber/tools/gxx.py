#
# Copyright (c) 2016 Stefan Seefeld
# All rights reserved.
#
# This file is part of Faber. It is made available under the
# Boost Software License, Version 1.0.
# (Consult LICENSE or http://www.boost.org/LICENSE_1_0.txt)

from ..action import action
from ..feature import set, map, translate, select_if
from ..artefact import artefact
from .. import types
from ..assembly import implicit_rule as irule
from .. import engine
from . import compiler
from .cxx import *
from .gcc import validate

class compile(action):

    command = 'g++ $(cppflags) $(cxxflags) -c -o $(<) $(>)'
    cppflags = map(compiler.cppflags)
    cppflags += map(compiler.define, translate, prefix='-D')
    cppflags += map(compiler.include, translate, prefix='-I')
    cxxflags = map(compiler.cxxflags)
    cxxflags += map(compiler.link, select_if, 'shared', '-fPIC')


class link(action):

    command = 'g++ $(ldflags) -o $(<) $(>) $(libs)'
    ldflags = map(compiler.ldflags)
    ldflags += map(compiler.linkpath, translate, prefix='-L')
    ldflags += map(compiler.link, select_if, 'shared', '-shared')
    libs = map(compiler.libs, translate, prefix='-l')
    
    def submit(self, artefacts, sources, module):
        # sources may contain object files as well as libraries
        # Separate the two, and add the libraries to the libs variable.

        src, linkpath, libs = gxx.split_libs(sources)
        fs = set(compiler.libs(*libs), compiler.linkpath(*linkpath))
        for t in artefacts:
            t.features += fs
        action.submit(self, artefacts, src, module)


class gxx(cxx):

    compile = compile()
    archive = action('ar rc $(<) $(>)')
    link = link()

    def __init__(self, name='g++', command=None, version='', features=()):

        command, version, features = validate(command or 'g++', version, features)
        cxx.__init__(self, name=name, version=version)
        self.features |= features
        if command:
            # if command is of the form <prefix>-g++, make sure
            # to adjust the names of the other tools of the toolchain.
            prefix = command[:-3] if command.endswith('g++') else ''
            self.compile.subst('g++', command)
            self.archive.subst('ar', prefix + 'ar')
            self.link.subst('g++', command)

        irule(types.obj, types.cxx, self.compile)
        irule(types.lib, types.obj, self.archive)
        irule(types.bin, (types.obj, types.dso, types.lib), self.link)
        irule(types.dso, (types.obj, types.dso), self.link)
