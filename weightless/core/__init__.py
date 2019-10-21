## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015 Seecr (Seek You Too B.V.) http://seecr.nl
#
# This file is part of "Weightless"
#
# "Weightless" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Weightless" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Weightless"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

VERSION='$Version: x.y.z$'[9:-1].strip() # Modified by package scripts

from functools import wraps
from types import GeneratorType, FunctionType

from os.path import dirname, abspath, isdir, join            #DO_NOT_DISTRIBUTE
from sys import version_info                                 #DO_NOT_DISTRIBUTE
# TS: FIXME Re-enable When Py3 stuff works.
print("Hello, re-enable C-building stuffs")
#pycmd = "python%s.%s" % version_info[:2]                     #DO_NOT_DISTRIBUTE
#_mydir = abspath(dirname(__file__))                          #DO_NOT_DISTRIBUTE
#_projectdir = dirname(dirname(_mydir))                       #DO_NOT_DISTRIBUTE
#if isdir(join(_mydir, '.svn')) or isdir(join(_projectdir, '.git')):  #DO_NOT_DISTRIBUTE
#    from os import system                                    #DO_NOT_DISTRIBUTE
#    status = system(                                         #DO_NOT_DISTRIBUTE
#        "cd %s/../..; %s setup.py build_ext --inplace"       #DO_NOT_DISTRIBUTE
#        % (abspath(dirname(__file__)), pycmd))               #DO_NOT_DISTRIBUTE
#    if status > 0:                                           #DO_NOT_DISTRIBUTE
#        import sys                                           #DO_NOT_DISTRIBUTE
#        sys.exit(status)                                     #DO_NOT_DISTRIBUTE

import platform
if hasattr(platform, 'python_implementation'):
    cpython = platform.python_implementation() == "CPython"
elif hasattr(platform, 'system'):
    cpython = platform.system() != "Java"
else:
    cpython = False

try:
    from os import getenv
    if getenv('WEIGHTLESS_COMPOSE_TEST') == 'PYTHON':
        raise ImportError('Python compose for testing purposes')
    from .ext import compose as _compose, local, tostring, Yield, is_generator, DeclineMessage
    cextension = True
    ComposeType = _compose
except ImportError as e:
    from warnings import warn
    warn("Using Python version of compose(), local() and tostring()", stacklevel=2)
    def is_generator(o):
        return type(o) is GeneratorType
    class DeclineMessage(Exception):
        pass
    from ._compose_py import compose as _compose, Yield, value_with_pushback
    from ._local_py import local
    from ._tostring_py import tostring
    cextension = False
    ComposeType = GeneratorType

def compose(X, *args, **kwargs):
    if type(X) == FunctionType: # compose used as decorator
        @wraps(X)
        def helper(*args, **kwargs):
            return _compose(X(*args, **kwargs))
        return helper
    elif is_generator(X):
        return _compose(X, *args, **kwargs)
    raise TypeError("compose() expects generator, got %s" % repr(X))

def maybe_str_to_bytes(v):
    if isinstance(v, str):
        return v.encode()
    return v

#from compose import compose, local, tostring, Yield
from .utils import identify, autostart, retval, consume, asList, asString
from ._observable import Observable, Transparent, be, methodOrMethodPartialStr, NoneOfTheObserversRespond

