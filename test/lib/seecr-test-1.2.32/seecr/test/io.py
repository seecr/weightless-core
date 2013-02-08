## begin license ##
# 
# "Seecr Test" provides test tools. 
# 
# Copyright (C) 2012 Seecr (Seek You Too B.V.) http://seecr.nl
# 
# This file is part of "Seecr Test"
# 
# "Seecr Test" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# "Seecr Test" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with "Seecr Test"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# 
## end license ##

from __future__ import with_statement

import sys

from StringIO import StringIO

from contextlib import contextmanager


@contextmanager
def stderr_replaced():
    oldstderr = sys.stderr
    mockStderr = StringIO()
    sys.stderr = mockStderr
    try:
        yield mockStderr
    finally:
        sys.stderr = oldstderr

def stderr_replace_decorator(func):
    def wrapper(*args, **kwargs):
        with stderr_replaced():
            return func(*args, **kwargs)
    return wrapper

@contextmanager
def stdout_replaced():
    oldstdout = sys.stdout
    mockStdout = StringIO()
    sys.stdout = mockStdout
    try:
        yield mockStdout
    finally:
        sys.stdout = oldstdout

def stdout_replace_decorator(func):
    def wrapper(*args, **kwargs):
        with stdout_replaced():
            return func(*args, **kwargs)
    return wrapper
