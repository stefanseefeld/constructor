#
# Copyright (c) 2016 Stefan Seefeld
# All rights reserved.
#
# This file is part of Faber. It is made available under the
# Boost Software License, Version 1.0.
# (Consult LICENSE or http://www.boost.org/LICENSE_1_0.txt)

from ..action import action
from ..feature import set, map, translate, select_if
from .. import types
from ..assembly import implicit_rule as irule
from . import compiler
from .cc import *
import os.path
import os
import subprocess
import re

# known architectures for each machine type
marchs = dict(x86_64=['x86_64', 'x86'],
              w64=['w64', 'w32'])

# compiler flags per architecture
arch_flags = dict(x86_64=['-m64'],
                  x86=['-m32'],
                  w64=['-m64'],
                  w32=['-m32'])


def validate(cls, command, version, features):

    features = set.instantiate(features)
    version = version or cls.find_version_requirement(features)
    v = subprocess.check_output([command, '-dumpversion']).decode().strip()
    m = subprocess.check_output([command, '-dumpmachine']).decode().strip()
    if version and v != version:
        raise ValueError('{} version mismatch: expected {}, got {}'
                         .format(command, version, v))
    else:
        version = v
    cpu, vendor, os = re.match('(\w+)-(\w+)-(\w+)', m).groups()
    if os == 'mingw32':
        os = 'Windows'
        machine = 'w64'
    else:
        machine = cpu

    if machine not in marchs:
        raise ValueError('Unsupported machine type {}'.format(machine))
    if 'target' in features:
        arch = str(features.target.arch)
        if arch not in marchs[machine]:
            raise ValueError('Unsupported target architecture {}'.format(arch))
        features |= compiler.target(os=os)
    else:
        arch=marchs[machine][0]
        features |= compiler.target(arch=arch, os=os)

    features |= compiler.cxxflags(*arch_flags[arch])
    features |= compiler.ldflags(*arch_flags[arch])

    return command, version, features


class makedep_wrapper(action):
    """This is a wrapper around `cc -MM ...` to normalize the output and
    make it portable across compilers."""

    def __init__(self, cmd):
        action.__init__(self, cmd.name, self.makedep)
        self.cmd = cmd

    def map(self, fs):
        return self.cmd.map(fs)  # just forward variables from makedep

    def makedep(self, targets, sources):
        dfile = targets[0]._filename
        self.cmd(targets, sources)
        with open(dfile) as f:
            out = ''.join(f.readlines())
        lines = out.split('\\')
        # remove the first two tokens, e.g.
        # '<file>.o:' and '<file>.c'
        lines[0] = lines[0].split(' ', 2)
        if len(lines[0]) == 3:
            lines[0] = lines[0][2]
        else:
            del lines[0]
        # flatten listing to contain one header per item
        headers = [h for l in lines for h in l.split()]
        # filter out system headers
        # TODO: make this configurable
        headers = [h for h in headers if not h.startswith('/usr/include')]
        # header paths are relative to the toplevel srcdir,
        # while we need them to be relative to the current module
        base = targets[0].module.srcdir
        relpath = lambda f, base: f if os.path.isabs(f) else os.path.relpath(f, base)
        headers = [relpath(h, base) + '\n' for h in headers]
        with open(dfile, 'w') as f:
            f.writelines(headers)


class makedep(action):

    command = 'gcc $(cppflags) -MM -o $(<) $(>)'
    cppflags = map(compiler.cppflags)
    cppflags += map(compiler.define, translate, prefix='-D')
    cppflags += map(compiler.include, translate, prefix='-I')


class compile(action):

    command = 'gcc $(cppflags) $(cflags) -c -o $(<) $(>)'
    cppflags = map(compiler.cppflags)
    cppflags += map(compiler.define, translate, prefix='-D')
    cppflags += map(compiler.include, translate, prefix='-I')
    cflags = map(compiler.cflags)
    cflags += map(compiler.link, select_if, 'shared', '-fPIC')


class link(action):

    command = 'gcc $(ldflags) -o $(<) $(>) $(libs)'
    ldflags = map(compiler.ldflags)
    ldflags += map(compiler.linkpath, translate, prefix='-L')
    ldflags += map(compiler.link, select_if, 'shared', '-shared')
    libs = map(compiler.libs, translate, prefix='-l')

    def submit(self, targets, sources):
        # sources may contain object files as well as libraries
        # Separate the two, and add the libraries to the libs variable.

        src, linkpath, libs = gcc.split_libs(sources)
        linkpath = [compiler.linkpath(l, base='') for l in linkpath]
        libs = [compiler.libs(l) for l in libs]
        fs = set(*libs + linkpath)
        for t in targets:
            t.features |= fs
        action.submit(self, targets, src)


class gcc(cc):

    makedep = makedep_wrapper(makedep())
    compile = compile()
    archive = action('ar rc $(<) $(>)')
    link = link()

    def __init__(self, name='gcc', command=None, version='', features=()):

        command, version, features = validate(self.__class__, command or 'gcc',
                                              version, features)
        cc.__init__(self, name=name, version=version)
        self.features |= features
        if command:
            # if command is of the form <prefix>-g++, make sure
            # to adjust the names of the other tools of the toolchain.
            prefix = command[:-3] if command.endswith('gcc') else ''
            self.compile.subst('gcc', command)
            self.archive.subst('ar', prefix + 'ar')
            self.link.subst('gcc', command)

        irule(self.compile, types.obj, types.c)
        irule(self.archive, types.lib, types.obj)
        irule(self.link, types.bin, (types.obj, types.dso, types.lib))
        irule(self.link, types.dso, (types.obj, types.dso))