#
# Copyright (c) 2016 Stefan Seefeld
# All rights reserved.
#
# This file is part of Faber. It is made available under the
# Boost Software License, Version 1.0.
# (Consult LICENSE or http://www.boost.org/LICENSE_1_0.txt)

from . import compiler
from ..action import action
import logging

logger = logging.getLogger('tools')


class cxx(compiler.compiler):
    """C++ compiler base-class.
    As an abstract base-class it declares the actions all subclasses need to provide,
    without implementing them.

    Build scripts thus can reference `cxx.compile` et al., which the runtime will
    substitute by an appropriate compiler instance, if available (or fail to build)."""

    # Scan source files for header dependencies
    makedep = action()
    # Build object files from C++ source files.
    compile = action()
    # Build (static) library archives from object files.
    archive = action()
    # Link binaries (executables or shared libraries).
    link = action()

    @classmethod
    def instance(cls, fs=None):
        """Try to find a compiler instance for the current platform."""

        if cls is cxx and not cls.instantiated(fs):
            # we can't instantiate this class directly, so try to find
            # a subclass...
            logger.info('trying to instantiate a default C++ compiler')
            import sys
            if sys.platform == 'win32':
                cls.try_instantiate('msvc', fs)
            cls.try_instantiate('gxx', fs)
            cls.try_instantiate('clangxx', fs)
            if not cls.instantiated(fs):
                msg = 'no C++ compiler found'
                msg += ' matching {}.'.format(fs.essentials()) if fs else '.'
                raise RuntimeError(msg)
        return super(cxx, cls).instance(fs)
