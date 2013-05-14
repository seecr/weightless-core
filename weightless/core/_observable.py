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
from traceback import format_exception
from functools import partial

from weightless.core.compose import isGeneratorOrComposed


class NoneOfTheObserversRespond(Exception):
    """Must not be thrown anywhere outside of the Observable
    implementation. It is exposed only so that it can be caught in 
    specific components, typically to be able to opt out of some 
    received message by raising DeclineMessage."""

    def __init__(self, unansweredMessage, nrOfObservers):
        Exception.__init__(self, 'None of the %d observers respond to %s(...)' % (nrOfObservers, unansweredMessage))


class _DeclineMessage(Exception):
    """Should be thrown by a component that wishes to opt out of a 
    message received through 'any' or 'call' that it can't or doesn't
    wish to handle after all.
    
    One reason might be that none of this components' observers responds
    to the message after being 'forwarded' (as signalled by a 
    NoneOfTheObserversRespond exception). For an example, please refer
    to the code of Transparent below.
    
    The exception only ever needs a single instance. For convenience and
    aesthetics this single instance is named as a class."""
DeclineMessage = _DeclineMessage()


class Defer(object):
    def __init__(self, observable, msgclass, filter=bool):
        self._observable = observable
        self._msgclass = msgclass
        self._filter = filter

    def observers(self):
        return (o for o in self._observable.observers() if self._filter(o))

    def __getattr__(self, attr):
        return self._msgclass(self, attr)

    def __getitem__(self, target):
        return Defer(self._observable, self._msgclass,
                filter=lambda o: hasattr(o, "observable_name") and o.observable_name() == target)

    def unknown(self, message, *args, **kwargs):
        try:
            return self._msgclass(self, message)(*args, **kwargs)
        except:
            c, v, t = exc_info(); raise c, v, t.tb_next


def handleNonGeneratorGeneratorExceptions(method, clazz, value, traceback):
    excStr = ''.join(format_exception(clazz, value, traceback))
    raise AssertionError("Non-Generator %s should not have raised Generator-Exception:\n%s" % (methodOrMethodPartialStr(method), excStr))

class MessageBase(object):
    def __init__(self, defer, message):
        self._defer = defer
        self._message = message

    def all(self, *args, **kwargs):
        for observer in self._defer.observers():
            try: method = getattr(observer, self._message)
            except AttributeError:
                try: 
                    method = partial(getattr(observer, self.altname), self._message)
                except AttributeError:
                    continue 
            try:
                try:
                    result = method(*args, **kwargs)
                except (StopIteration, GeneratorExit):  #fail on illogical method-results for non-Generators
                    c, v, t = exc_info()
                    handleNonGeneratorGeneratorExceptions(method, c, v, t.tb_next)
                self.verifyMethodResult(method, result)
                _ = yield result
            except _DeclineMessage:
                continue
            except:
                c, v, t = exc_info(); raise c, v, t.tb_next
            assert _ is None, "%s returned '%s'" % (methodOrMethodPartialStr(method), _)

    def any(self, *args, **kwargs):
        try:
            for r in self.all(*args, **kwargs):
                try:
                    result = yield r
                    raise StopIteration(result)
                except _DeclineMessage:
                    continue
        except:
            c, v, t = exc_info(); raise c, v, t.tb_next
        raise NoneOfTheObserversRespond(
                unansweredMessage=self._message, 
                nrOfObservers=len(list(self._defer.observers())))

    def verifyMethodResult(self, method, result):
        assert isGeneratorOrComposed(result), "%s should have resulted in a generator." % methodOrMethodPartialStr(method)

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
    def once(self, *args, **kwargs):
        done = set()
        return self._callonce(self._defer.observers(), args, kwargs, done)
    __call__ = once

    def _callonce(self, observers, args, kwargs, done):
        for observer in (o for o in observers if o not in done):
            done.add(observer)
            try:
                method = getattr(observer, self._message)
            except AttributeError:
                pass
            else:
                try:  # Added for framework off-the-stacktrace
                    try:
                        _ = methodResult = method(*args, **kwargs)
                    except (StopIteration, GeneratorExit):  #fail on illogical method-results for non-Generators
                        c, v, t = exc_info()
                        handleNonGeneratorGeneratorExceptions(method, c, v, t.tb_next)
                    if isGeneratorOrComposed(methodResult):
                        _ = yield methodResult
                except:
                    c, v, t = exc_info(); raise c, v, t.tb_next
                # assert outside of removal to keep raising-file-line in the trace (for clarity) [ok?]
                assert _ is None, "%s returned '%s'" % (methodOrMethodPartialStr(method), _)
            if isinstance(observer, Observable):
                try:  # Added for framework off-the-stacktrace
                    _ = yield self._callonce(observer._observers, args, kwargs, done)
                except:
                    c, v, t = exc_info(); raise c, v, t.tb_next
                # assert outside of removal to keep raising-file-line in the trace (for clarity) [ok?]
                assert _ is None, "OnceMessage of %s returned '%s', but must always be None" % (self._defer._observable, _)


class Observable(object):
    def __init__(self, name=None):
        self._name = name
        self._observers = []
        self.all = Defer(self, AllMessage)
        self.any = Defer(self, AnyMessage)
        self.do = Defer(self, DoMessage)
        self.call = Defer(self, CallMessage)
        self.once = Defer(self, OnceMessage)

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

    def addStrand(self, strand, helicesDone):
        for helix in strand:
            self.addObserver(_beRecursive(helix, helicesDone))

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

def methodOrMethodPartialStr(f):
    if type(f) == partial:
        f = f.func
    return str(f)

