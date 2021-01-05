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

from functools import wraps
from re import compile
from weightless.core import compose

from inspect import isgeneratorfunction

def return_(*args):
    raise StopIteration(*args)

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

def asBytes(g):
    return b''.join(compose(g))

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
    if isinstance(regexp, str):
        regexp = compile(regexp)
    match = None
    message = ''
    while not match:
        if maximum and len(message) > maximum:
            raise OverflowError('no match after %s bytes' % len(message))
        msg = yield
        if msg == None:
            break
        message += msg
        match = regexp.match(message)
    if not match:
        raise Exception("no match at eof: '%s'" % message)
    args = match.groupdict()
    rest = message[match.end():]
    return (args, rest) if rest else args

def readAll():
    data = []
    try:
        while True:
            data.append((yield))
    except StopIteration:
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
            return None, tail, message
        if message and not tail:
            return None, message
        if tail and not message:
            return None, tail
        return
    if tail:
        return None, tail

__all__ = ['return_', 'identify', 'autostart', 'retval', 'consume', 'asList', 'asString', 'asBytes', 'copyBytes', 'readRe', 'readAll', 'isgeneratorfunction']
