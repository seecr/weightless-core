## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015, 2020-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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

from warnings import warn
def is_generator(o):
    return type(o) is GeneratorType
class DeclineMessage(Exception):
    pass

import platform
if hasattr(platform, 'python_implementation'):
    cpython = platform.python_implementation() == "CPython"
elif hasattr(platform, 'system'):
    cpython = platform.system() != "Java"
else:
    cpython = False

from ._compose_py import compose as _compose, Yield
from ._local_py import local
from ._tostring_py import tostring

def compose(X, *args, **kwargs):
    if type(X) == FunctionType: # compose used as decorator
        @wraps(X)
        def helper(*args, **kwargs):
            return _compose(X(*args, **kwargs))
        return helper
    elif is_generator(X):
        return _compose(X, *args, **kwargs)
    raise TypeError("compose() expects generator, got %s" % repr(X))

from .utils import identify, autostart, retval, consume, asList, asString, asBytes, return_
from ._observable import Observable, Transparent, be, methodOrMethodPartialStr, NoneOfTheObserversRespond

