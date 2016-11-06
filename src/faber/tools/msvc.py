#
# Copyright (c) 2016 Stefan Seefeld
# All rights reserved.
#
# This file is part of Faber. It is made available under the
# Boost Software License, Version 1.0.
# (Consult LICENSE or http://www.boost.org/LICENSE_1_0.txt)

from ..action import action
from ..feature import set as fset, map, translate, select_if
from ..artefact import artefact
from . import compiler
from .cc import *
from .cxx import *
from os.path import join, normpath, pathsep, exists
try:
    import winreg
except ImportError:  # python 2
    import _winreg as winreg
from collections import OrderedDict
from subprocess import *


class compile(action):

    command = 'cl /nologo $(cppflags) $(cflags) $(cxxflags) /GR /MD /EHsc /c /Fo$(<) $(>)'
    cppflags = map(compiler.cppflags)
    cppflags += map(compiler.define, translate, prefix='/D')
    cppflags += map(compiler.include, translate, prefix='/I"', suffix='"')
    cflags = map(compiler.cflags)
    cxxflags = map(compiler.cxxflags)


class link(action):

    command = 'link /nologo $(ldflags) /out:$(<) $(>) $(libs)'
    ldflags = map(compiler.ldflags)
    ldflags += map(compiler.linkpath, translate, prefix='/libpath:"', suffix='"')
    ldflags += map(compiler.link, select_if, 'shared', '/DLL')
    libs = map(compiler.libs, translate, suffix='.lib')

    def submit(self, targets, sources):
        # sources may contain object files as well as libraries
        # Separate the two, and add the libraries to the libs variable.

        src, linkpath, libs = msvc.split_libs(sources)
        linkpath = [compiler.linkpath(l, base='') for l in linkpath]
        libs = [compiler.libs(l) for l in libs]
        fs = fset(*libs + linkpath)
        for t in targets:
            t.features |= fs
        action.submit(self, targets, src)


class archive(action):

    command = 'lib /nologo /out:$(<) $(>)'


class msvc(cc, cxx):

    # available toolchains by version
    _toolchains = OrderedDict()
    known_archs = ['x86_64', 'x86']
    win_archs = {'x86_64': 'x64',
                 'x86': 'x86'}

    compile = compile()
    archive = archive()
    link = link()

    @classmethod
    def split_libs(cls, sources):
        """split libraries from sources.
        Return (src, linkpath, libs)"""

        src = []
        libs = []
        linkpath = set()
        for s in sources:
            if isinstance(s, artefact):
                src.append(s)
            else:
                raise ValueError('Unknown type of source {}'.format(s))
        return src, linkpath, libs

    def __init__(self, name='msvc', command=None, version='', features=()):

        features = fset.instantiate(features)
        if not version:
            version = self.find_version_requirement(features)
        if not version and len(msvc._toolchains):
            version = list(msvc._toolchains)[0]
        arch = str(features.target.arch) if 'target' in features else None
        if arch and arch not in msvc._toolchains[version]:
            raise ValueError('MSVC {} does not support target architecture {}'
                             .format(version, arch))
        if arch:
            product_dir, path = msvc._toolchains[version][arch]
            features |= compiler.target(os='Windows')
        else:
            arch, (product_dir, path) = list(msvc._toolchains[version].items())[0]
            features |= compiler.target(arch=arch, os='Windows')
        super(msvc, self).__init__(name=name, version=version)
        self.features |= features

        self.compile.subst('cl', '"{}\\{}"'.format(path, 'cl'))
        self.archive.subst('lib', '"{}\\{}"'.format(path, 'lib'))
        self.link.subst('link', '"{}\\{}"'.format(path, 'link'))

        # Extract INCLUDE, LIB, and LIBPATH from setup script
        setup = join(product_dir, 'vcvarsall.bat')
        output = check_output([setup, msvc.win_archs[arch], '&', 'set']).decode()
        vars = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
        self.vars = {k: vars[k] for k in ('INCLUDE', 'LIB', 'LIBPATH')}
        include = compiler.include(*[i for i in self.vars['INCLUDE'].split(pathsep) if i])
        linkpath = compiler.linkpath(*[l for l in self.vars['LIB'].split(pathsep) if l])
        linkpath += compiler.linkpath(*[l for l in self.vars['LIBPATH'].split(pathsep) if l])
        self.features += include
        self.features += linkpath

    @classmethod
    def find_path(cls, product_dir, arch):
        setup = join(product_dir, 'vcvarsall.bat')
        output = check_output([setup, arch, '&', 'set']).decode()
        vars = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
        path = vars['Path']
        for p in path.split(pathsep):
            if exists(join(p, 'cl.exe')):
                return p

    @classmethod
    def discover(cls):

        # Known toolset versions, in order of preference.
        known_versions = ['15.0',
                          '14.0',
                          '12.0',
                          '11.0',
                          '10.0',
                          '10.0express',
                          '9.0',
                          '9.0express',
                          '8.0',
                          '8.0express',
                          '7.1',
                          '7.1toolkit',
                          '7.0',
                          '6.0']

        # Names of registry keys containing the Visual C++ installation path (relative
        # to "HKEY_LOCAL_MACHINE\SOFTWARE\\Microsoft").
        reg_keys = {'6.0': 'VisualStudio\\6.0\\Setup\\Microsoft Visual C++',
                    '7.0': 'VisualStudio\\7.0\\Setup\\VC',
                    '7.1': 'VisualStudio\\7.1\\Setup\\VC',
                    '8.0': 'VisualStudio\\8.0\\Setup\\VC',
                    '8.0express': 'VCExpress\\8.0\\Setup\\VC',
                    '9.0': 'VisualStudio\\9.0\\Setup\\VC',
                    '9.0express': 'VCExpress\\9.0\\Setup\\VC',
                    '10.0': 'VisualStudio\\10.0\\Setup\\VC',
                    '10.0express': 'VCExpress\\10.0\\Setup\\VC',
                    '11.0': 'VisualStudio\\11.0\\Setup\\VC',
                    '12.0': 'VisualStudio\\12.0\\Setup\\VC',
                    '14.0': 'VisualStudio\\14.0\\Setup\\VC',
                    '15.0': 'VisualStudio\\15.0\\Setup\\VC'}

        for version in known_versions:
            cls._toolchains[version] = OrderedDict()
            for arch in msvc.known_archs:
                product_dir, path = None, None
                for x64elt in ('', 'Wow6432Node\\'):
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                            'SOFTWARE\\{}Microsoft\\{}'
                                            .format(x64elt, reg_keys[version])) as key:
                            product_dir = winreg.QueryValueEx(key, "ProductDir")[0]
                            path = cls.find_path(product_dir, msvc.win_archs[arch])
                    except Exception:
                        pass
                if path:
                    cls._toolchains[version][arch] = (normpath(product_dir), normpath(path))
            if not cls._toolchains[version]:
                # remove empty entries
                del cls._toolchains[version]


# If this module is imported, assume we are running inside Windows
msvc.discover()


if __name__ == '__main__':

    print('found MSVC toolchains:')
    for v in msvc._toolchains:
        for a, p in msvc._toolchains[v].items():
            print('  version {} ({}) in {}'.format(v, a, p[1]))
