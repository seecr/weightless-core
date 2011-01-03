## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2010 Seek You Too (CQ2) http://www.cq2.nl
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

from sys import exc_info
from unittest import TestCase
from re import sub
from traceback import format_exc

from cq2utils import CallTrace, CQ2TestCase

from weightless import Reactor, Suspend, HttpServer

class MockSocket(object):
    def close(self):
        self.closed = True

def mockselect(readers, writers, x, timeout):
    return readers, writers, x

fileDict = {
    '__file__': mockselect.func_code.co_filename, # Hacky, but sys.modules[aModuleName].__file__ is inconsistent with traceback-filenames
    'suspend.py': Suspend.__call__.func_code.co_filename,
}


class SuspendTest(CQ2TestCase):

    def testReactorSuspend(self):
        handle = ['initial value']
        reactor = Reactor(select_func=mockselect)
        def callback():
            handle[0] = reactor.suspend()
        sok = MockSocket()
        reactor.addReader(sok, callback)
        self.assertTrue(sok in reactor._readers)
        reactor.step()
        self.assertTrue(sok not in reactor._readers)

        sok = MockSocket()
        reactor.addWriter(sok, callback)
        self.assertTrue(sok in reactor._writers)
        reactor.step()
        self.assertTrue(sok not in reactor._writers)
        self.assertTrue(handle[0] != None)
        self.assertTrue(handle[0] != 'initial value')

    def testReactorResumeWriter(self):
        handle = ['initial value']
        reactor = Reactor(select_func=mockselect)
        def callback():
            handle[0] = reactor.suspend()
            yield
            yield
        sok = MockSocket()
        reactor.addWriter(sok, callback().next)
        reactor.step()
        reactor.resumeWriter(handle[0])
        reactor.step()
        self.assertTrue(sok in reactor._writers)
        self.assertTrue(sok not in reactor._readers)
        self.assertRaises(KeyError, reactor.resumeWriter, handle[0])

    def testWrongUseAfterSuspending(self):
        reactor = Reactor(select_func=mockselect)
        handle = ['initial value']
        def callback():
            handle[0] = reactor.suspend()
        sok = MockSocket()
        reactor.addWriter(sok, callback)
        reactor.step()
        self.assertEquals(sok, handle[0])
        try:
            reactor.addWriter(sok, callback)
            self.fail("Exception not raised")
        except ValueError, e:
            self.assertEquals('Socket is suspended', str(e))
        try:
            reactor.addReader(sok, callback)
            self.fail("Exception not raised")
        except ValueError, e:
            self.assertEquals('Socket is suspended', str(e))

    def testShutdownReactor(self):
        reactor = Reactor(select_func=mockselect)
        sok1 = MockSocket()
        sok2 = MockSocket()
        sok3 = MockSocket()
        def callback():
            reactor.suspend()
        reactor.addReader(sok1, lambda: None)
        reactor.addWriter(sok2, lambda: None)
        reactor.addWriter(sok3, callback)
        reactor.step()
        self.assertFalse(sok3 in reactor._readers)
        self.assertFalse(sok3 in reactor._writers)
        reactor.shutdown() 
        self.assertTrue(sok1.closed)
        self.assertTrue(sok2.closed)
        self.assertTrue(sok3.closed)

    def testSuspendProtocol(self):
        reactor = Reactor(select_func=mockselect)
        suspend = Suspend()
        def handler(**httpvars):
            yield 'before suspend'
            yield suspend
            yield "result = %s" % suspend.getResult()
            yield 'after suspend'
        listener = MyMockSocket()
        port = 9
        httpserver = HttpServer(reactor, port, handler, sok=listener)
        reactor.removeReader(listener) # avoid new connections
        httpserver._accept()
        reactor.step()
        reactor.step()
        self.assertEquals(1, len(reactor._writers))
        reactor.step()
        self.assertEquals(reactor, suspend._reactor)
        self.assertEquals(0, len(reactor._writers))
        suspend.resume('RESPONSE')
        reactor.step()
        reactor.step()
        reactor.step()
        self.assertEquals(['before suspend', 'result = RESPONSE', 'after suspend'], listener.data)

    def testSuspendProtocolWithThrow(self):
        reactor = Reactor(select_func=mockselect)
        suspend = Suspend()
        def handler(**httpvars):
            yield 'before suspend'
            yield suspend
            try:
                suspend.getResult()
                self.fail()
            except ValueError, e:
                tbstring = format_exc()
                yield "result = %s" % tbstring
            yield 'after suspend'
        listener = MyMockSocket()
        port = 9
        httpserver = HttpServer(reactor, port, handler, sok=listener)
        reactor.removeReader(listener) # avoid new connections
        httpserver._accept()
        reactor.step()
        reactor.step()
        self.assertEquals(1, len(reactor._writers))
        reactor.step()
        self.assertEquals(reactor, suspend._reactor)
        self.assertEquals(0, len(reactor._writers))
        def raiser():
            raise ValueError("BAD VALUE")
        try:
            raiser()
        except ValueError, e:
            exc_type, exc_value, exc_traceback = exc_info()
            suspend.throw(exc_type, exc_value, exc_traceback)
        reactor.step()
        reactor.step()
        reactor.step()
        expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
  File "%(__file__)s", line 152, in handler
    suspend.getResult()
  File "%(__file__)s", line 172, in testSuspendProtocolWithThrow
    raiser()
  File "%(__file__)s", line 170, in raiser
    raise ValueError("BAD VALUE")
ValueError: BAD VALUE
        """ % fileDict)
        self.assertEquals(3, len(listener.data))
        self.assertEquals('before suspend', listener.data[0])
        self.assertEqualsWS("result = %s" % expectedTraceback, ignoreLineNumbers(listener.data[1]))
        self.assertEquals('after suspend', listener.data[2])

    def testSuspendThrowBackwardsCompatibleWithInstanceOnlyThrow_YouWillMissTracebackHistory(self):
        reactor = Reactor(select_func=mockselect)
        suspend = Suspend()
        def handler(**httpvars):
            yield 'before suspend'
            yield suspend
            try:
                suspend.getResult()
                self.fail()
            except ValueError, e:
                tbstring = format_exc()
                yield "result = %s" % tbstring
            yield 'after suspend'
        listener = MyMockSocket()
        port = 9
        httpserver = HttpServer(reactor, port, handler, sok=listener)
        reactor.removeReader(listener) # avoid new connections
        httpserver._accept()
        reactor.step()
        reactor.step()
        self.assertEquals(1, len(reactor._writers))
        reactor.step()
        self.assertEquals(reactor, suspend._reactor)
        self.assertEquals(0, len(reactor._writers))
        def raiser():
            raise ValueError("BAD VALUE")
        try:
            raiser()
        except:
            exc_value = exc_info()[1]
            suspend.throw(exc_value)
        reactor.step()
        reactor.step()
        reactor.step()
        expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
  File "%(__file__)s", line 201, in handler
    suspend.getResult()
  File "%(suspend.py)s", line 62, in getResult
    raise exc_tuple[0], exc_tuple[1], exc_tuple[2]
ValueError: BAD VALUE
        """ % fileDict)
        self.assertEquals(3, len(listener.data))
        self.assertEquals('before suspend', listener.data[0])
        self.assertEqualsWS("result = %s" % expectedTraceback, ignoreLineNumbers(listener.data[1]))
        self.assertEquals('after suspend', listener.data[2])

    def testGetResult(self):
        reactor = CallTrace('reactor')
        s = Suspend()
        s(reactor, whenDone=lambda:None)
        s.resume('state')
        self.assertEquals('state', s.getResult())

    def testGetNoneResult(self):
        reactor = CallTrace('reactor')
        s = Suspend()
        s(reactor, whenDone=lambda:None)
        s.resume()
        self.assertEquals(None, s.getResult())

    def testGetResultRaisesException(self):
        reactor = CallTrace('reactor')
        s = Suspend()
        s(reactor, whenDone=lambda:None)
        s.throw(ValueError('bad value'))
        self.assertRaises(ValueError, s.getResult)

    def testCleanUp(self):
        reactor = Reactor(select_func=mockselect)
        def handler():
            reactor.suspend()
            yield
        reactor.addWriter(1, lambda: None)
        reactor.addReader(2, lambda: None)
        reactor.addReader(3, handler().next)
        reactor.step()
        self.assertTrue(1 in reactor._writers)
        reactor.cleanup(1)
        self.assertFalse(1 in reactor._writers)
        self.assertTrue(2 in reactor._readers)
        reactor.cleanup(2)
        self.assertFalse(2 in reactor._readers)
        self.assertTrue(3 in reactor._suspended)
        reactor.cleanup(3)
        self.assertFalse(3 in reactor._suspended)

class MyMockSocket(object):
    def __init__(self, data=None):
        self.data = [] if data is None else data
    def accept(self):
        return MyMockSocket(self.data), None
    def setsockopt(self, *args):
        pass
    def recv(self, *args):
        return 'GET / HTTP/1.0\r\n\r\n'
    def getpeername(self):
        return 'itsme'
    def shutdown(self, *args):
        pass
    def close(self):
        pass
    def send(self, chunk, options):
        self.data.append(chunk)
        return len(chunk)

def ignoreLineNumbers(s):
    return sub("line \d+,", "line [#],", s)

