# -*- coding: utf-8 -*-
## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2006-2010 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011 Seecr http://seecr.nl
# Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
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

from sys import exc_info
from functools import partial

from weightless.core import is_generator
from weightless.core import MessageBase
from weightless.core import NoneOfTheObserversRespond
from weightless.core import DeclineMessage
from utils import methodOrMethodPartialStr


from collections import defaultdict

class Defer(defaultdict):
    def __init__(self, observers, msgclass):
        __slots__ = ('_observers', '_msgclass')
        self._observers = tuple(observers)
        self._msgclass = msgclass

    def __getattr__(self, attr):
        msg = self._msgclass(self._observers, attr)
        setattr(self, attr, msg)
        return msg

    def __missing__(self, target):
        observers = (o for o in self._observers
            if hasattr(o, "observable_name") and o.observable_name() == target)
        d = Defer(observers, self._msgclass)
        self[target] = d
        return d

    def unknown(self, message, *args, **kwargs):
        try:
            return self._msgclass(self._observers, message)(*args, **kwargs)
        except:
            c, v, t = exc_info(); raise c, v, t.tb_next

class AllMessage(MessageBase):
    altname = 'all_unknown'
    __call__ = MessageBase.all

class AnyMessage(MessageBase):
    altname = 'any_unknown'
    __call__ = MessageBase.any

class CallMessage(MessageBase):
    altname = 'call_unknown'

    def call(self, *args, **kwargs):
        try:
            return self.any(*args, **kwargs).next()
        except:
            c, v, t = exc_info(); raise c, v, t.tb_next
    __call__ = call

    def verifyMethodResult(self, method, result):
        pass

class DoMessage(MessageBase):
    altname = 'do_unknown'

    def do(self, *args, **kwargs):
        try:
            for _ in self.all(*args, **kwargs):
                pass
        except:
            c, v, t = exc_info(); raise c, v, t.tb_next
    __call__ = do

    def verifyMethodResult(self, method, result):
        assert result is None, "%s returned '%s'" % (methodOrMethodPartialStr(method), result)

class OnceMessage(MessageBase):
    altname = ""

    def __init__(self, observers, *args, **kwargs):
        self._observers = observers
        super(OnceMessage, self).__init__(observers, *args, **kwargs)

    def once(self, *args, **kwargs):
        done = set()
        return self._callonce(self._observers, args, kwargs, done)
    __call__ = once

    def _callonce(self, observers, args, kwargs, done):
        for observer in (o for o in observers if o not in done):
            done.add(observer)
            try:
                method = getattr(observer, self._message)
            except AttributeError:
                pass
            else:
                _ = methodResult = method(*args, **kwargs)
                if is_generator(methodResult):
                    _ = yield methodResult
                assert _ is None, "%s returned '%s'" % (methodOrMethodPartialStr(method), _)
            if isinstance(observer, Observable):
                _ = yield self._callonce(observer._observers, args, kwargs, done)


class Observable(object):
    def __init__(self, name=None):
        __slots__ = ('_name', '_observers', 'all', 'any', 'do', 'call', 'once')
        self._name = name
        self._observers = []
        self.init_defers()

    def init_defers(self):
        self.all = Defer(self._observers, AllMessage)
        self.any = Defer(self._observers, AnyMessage)
        self.do = Defer(self._observers, DoMessage)
        self.call = Defer(self._observers, CallMessage)
        self.once = Defer(self._observers, OnceMessage)

    def observers(self):
        for observer in self._observers:
            yield observer

    def observable_name(self):
        return self._name

    def observable_setName(self, name):
        self._name = name
        return self

    def addObserver(self, observer):
        self._observers.append(observer)
        self.init_defers()

    def addStrand(self, strand, helicesDone):
        for helix in strand:
            self.addObserver(_beRecursive(helix, helicesDone))
        self.init_defers()

    def printTree(self, depth=0):
        def printInColor(ident, color, text):
            print ' '*ident, chr(27)+"[0;" + str(color) + "m", text, chr(27)+"[0m"
        print ' ' * depth, self.__repr__()
        for observer in self._observers:
            if hasattr(observer, 'printTree'):
                observer.printTree(depth=depth+1)
            else:
                printInColor(depth+1, 31, observer)

    def __repr__(self):
        return "%s(name=%s)" % (self.__class__.__name__, repr(self._name))


class Transparent(Observable):
    def all_unknown(self, message, *args, **kwargs):
        yield self.all.unknown(message, *args, **kwargs)
    def any_unknown(self, message, *args, **kwargs):
        try:
            response = yield self.any.unknown(message, *args, **kwargs)
        except NoneOfTheObserversRespond:
            raise DeclineMessage
        raise StopIteration(response)
    def do_unknown(self, message, *args, **kwargs):
        self.do.unknown(message, *args, **kwargs)
    def call_unknown(self, message, *args, **kwargs):
        try:
            return self.call.unknown(message, *args, **kwargs)
        except NoneOfTheObserversRespond:
            raise DeclineMessage

def be(strand):
    helicesDone = set()
    return _beRecursive(strand, helicesDone)

def _beRecursive(helix, helicesDone):
    if callable(helix):
        helix = helix(helicesDone)
    component = helix[0]
    strand = helix[1:]
    if not helix in helicesDone and strand:
        component.addStrand(strand, helicesDone)
        helicesDone.add(helix)
    return component
