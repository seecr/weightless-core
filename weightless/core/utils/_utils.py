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

from functools import wraps
from re import compile
from weightless.core import compose, value_with_pushback

from inspect import isgeneratorfunction


def retval(generator):
    g = compose(generator)
    try:
        while True:
            g.__next__()
    except StopIteration as e:
        return e.value

def consume(generator):
    for _ in compose(generator):
        pass

def asList(g):
    return list(compose(g))

def asString(g):
    return ''.join(compose(g))

def identify(generatorFunction):
    @wraps(generatorFunction)
    def helper(*args, **kwargs):
        g = generatorFunction(*args, **kwargs)
        g.__next__()
        g.send(g)
        return g
    return helper

def autostart(generatorFunction):
    @wraps(generatorFunction)
    def helper(*args, **kwargs):
        g = generatorFunction(*args, **kwargs)
        g.__next__()
        return g
    return helper

def readRe(regexp, maximum=None):
    if isinstance(regexp, (str, bytes)):
        regexp = compile(regexp)
    is_bytes_re = isinstance(regexp.pattern, bytes)
    match = None
    message = b'' if is_bytes_re else ''
    while not match:
        if maximum and len(message) > maximum:
            raise OverflowError('no match after %s bytes' % len(message))
        msg = yield
        if msg == None:
            break
        message += msg
        match = regexp.match(message)
    if not match:
        raise Exception("no match at eof: '%s'" % str(message))
    args = match.groupdict()
    rest = message[match.end():]
    if rest:
        return value_with_pushback(args, rest)
    return args

def readAll():
    data = []
    try:
        while True:
            data.append((yield))
    except StopIteration:
        if data and isinstance(data[0], bytes):
            return b''.join(data)
        return ''.join(data)

def copyBytes(tosend, target):
    response, message, tail = None, None, None
    while tosend > 0:
        message = yield response
        head, tail = message[:tosend], message[tosend:]
        response = target.send(head)
        tosend -= len(head)

    if response:
        message = yield response
        if message and tail:
            return value_with_pushback(None, tail, message)
        if message and not tail:
            return value_with_pushback(None, message)
        if tail and not message:
            return value_with_pushback(None, tail)
        return

    if tail:
        return value_with_pushback(None, tail)
