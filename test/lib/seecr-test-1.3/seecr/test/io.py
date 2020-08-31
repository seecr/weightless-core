## begin license ##
#
# "Seecr Test" provides test tools.
#
# Copyright (C) 2012-2013 Seecr (Seek You Too B.V.) http://seecr.nl
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



import sys
from contextlib import contextmanager
from functools import wraps
from io import StringIO


def _replace_stream_factory(name):
    @contextmanager
    def stream_replace_contextmanager():
        mockStream, back = _set_replaced_stream(name)
        try:
            yield mockStream
        finally:
            back()

    def stream_replace(func=None):
        if func:
            @wraps(func)
            def wrapper(*args, **kwargs):
                with stream_replace_contextmanager():
                    return func(*args, **kwargs)
            return wrapper

        return stream_replace_contextmanager()

    return stream_replace

def _set_replaced_stream(name):
    stream = getattr(sys, name)
    def andBackAgain():
        setattr(sys, name, stream)

    streamReplacement = StringIO()
    setattr(sys, name, streamReplacement)
    return streamReplacement, andBackAgain

stderr_replaced = _replace_stream_factory('stderr')
stdout_replaced = _replace_stream_factory('stdout')

