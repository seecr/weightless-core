## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
from re import compile

def identify(generator):
    def helper(*args, **kwargs):
        g = generator(*args, **kwargs)
        g.next()
        g.send(g)
        return g
    return helper

def autostart(generator):
    def helper(*args, **kwargs):
        g = generator(*args, **kwargs)
        g.next()
        return g
    return helper

def readRe(regexp, maximum=None):
    if isinstance(regexp, basestring):
        regexp = compile(regexp)
    match = None
    message = ''
    while not match:
        if maximum and len(message) > maximum:
            raise OverflowError('no match after %s bytes' % len(message))
        message += yield
        match = regexp.match(message)
    args = match.groupdict()
    rest = message[match.end():]
    if rest:
        raise StopIteration(args, rest)
    raise StopIteration(args)

def readAll():
    data = []
    try:
        while True:
            data.append((yield))
    except StopIteration:
        raise StopIteration(''.join(data))

def copyBytes(tosend, target):
    response, message, tail = None, None, None
    while tosend > 0:
        message = yield response
        head, tail = message[:tosend], message[tosend:]
        response = target.send(head)
        tosend -= len(head)
    #try:
    #    response = target.throw(StopIteration())
    #except StopIteration:
    #    pass
    if response:
        message = yield response
        if message and tail:
            raise StopIteration(None, tail, message)
        if message and not tail:
            raise StopIteration(None, message)
        if tail and not message:
            raise StopIteration(None, tail)
        raise StopIteration()
    if tail:
        raise StopIteration(None, tail)

