## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2013 Seecr (Seek You Too B.V.) http://seecr.nl
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

import sys
from sys import exc_info
from io import StringIO

from re import sub
from traceback import format_exc, format_tb

from weightlesstestcase import WeightlessTestCase
from seecr.test import CallTrace

from weightless.io import Reactor, Suspend
from weightless.http import HttpServer

class MockSocket(object):
    def close(self):
        self.closed = True

def mockselect(readers, writers, x, timeout):
    return readers, writers, x

fileDict = {
    '__file__': mockselect.__code__.co_filename, # Hacky, but sys.modules[aModuleName].__file__ is inconsistent with traceback-filenames
    'suspend.py': Suspend.__call__.__code__.co_filename,
}

class SuspendTest(WeightlessTestCase):

    def testReactorSuspend(self):
        handle = ['initial value']
        with Reactor(select_func=mockselect, log=StringIO()) as reactor:
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
        with Reactor(select_func=mockselect, log=StringIO()) as reactor:
            def callback():
                handle[0] = reactor.suspend()
                yield
                yield
            sok = MockSocket()
            reactor.addWriter(sok, callback().__next__)
            reactor.step()
            reactor.resumeWriter(handle[0])
            reactor.step()
            self.assertTrue(sok in reactor._writers)
            self.assertTrue(sok not in reactor._readers)
            self.assertRaises(KeyError, reactor.resumeWriter, handle[0])

    def testReactorResumeReader(self):
        handle = ['initial value']
        with Reactor(select_func=mockselect, log=StringIO()) as reactor:
            def callback():
                handle[0] = reactor.suspend()
                yield
                yield
            sok = MockSocket()
            reactor.addReader(sok, callback().__next__)
            reactor.step()
            reactor.resumeReader(handle[0])
            reactor.step()
            self.assertFalse(sok in reactor._writers)
            self.assertTrue(sok in reactor._readers)
            self.assertRaises(KeyError, reactor.resumeReader, handle[0])

    def testReactorResumeProcess(self):
        log = StringIO()
        with Reactor(select_func=mockselect, log=log) as reactor:
            def callback():
                handle[0] = reactor.suspend()
                yield
                yield
            handle = [callback().__next__]
            sok = MockSocket()
            reactor.addProcess(handle[0])
            reactor.step()
            reactor.resumeProcess(handle[0])
            reactor.step()
            self.assertFalse(handle[0] in reactor._writers)
            self.assertFalse(handle[0] in reactor._readers)
            self.assertTrue(handle[0] in reactor._processes)
            self.assertRaises(KeyError, reactor.resumeProcess, handle[0])

    def testWrongUseAfterSuspending(self):
        with Reactor(select_func=mockselect, log=StringIO()) as reactor:
            handle = ['initial value']
            def callback():
                handle[0] = reactor.suspend()
            sok = MockSocket()
            reactor.addWriter(sok, callback)
            reactor.step()
            self.assertEqual(sok, handle[0])
            try:
                reactor.addWriter(sok, callback)
                self.fail("Exception not raised")
            except ValueError as e:
                self.assertEqual('Socket is suspended', str(e))
            try:
                reactor.addReader(sok, callback)
                self.fail("Exception not raised")
            except ValueError as e:
                self.assertEqual('Socket is suspended', str(e))

    def testShutdownReactor(self):
        def callback():
            reactor.suspend()
        log = StringIO()
        with Reactor(select_func=mockselect, log=log) as reactor:
            sok1 = MockSocket()
            sok2 = MockSocket()
            sok3 = MockSocket()
            reactor.addReader(sok1, lambda: None)
            reactor.addWriter(sok2, lambda: None)
            reactor.addWriter(sok3, callback)
            reactor.step()
            self.assertFalse(sok3 in reactor._readers)
            self.assertFalse(sok3 in reactor._writers)
            reactor.shutdown()
            self.assertTrue(str(sok1) in log.getvalue(), log.getvalue())
            self.assertTrue(str(sok2) in log.getvalue(), log.getvalue())
            self.assertTrue(str(sok3) in log.getvalue())
            self.assertTrue(sok1.closed)
            self.assertTrue(sok2.closed)
            self.assertTrue(sok3.closed)

    def testSuspendProtocol(self):
        suspend = Suspend()
        def handler(**httpvars):
            yield 'before suspend'
            yield suspend
            yield "result = %s" % suspend.getResult()
            yield 'after suspend'
        listener = MyMockSocket()
        port = 9
        with Reactor(select_func=mockselect, log=StringIO()) as reactor:
            with HttpServer(reactor, port, handler, sok=listener) as httpserver:
                httpserver.listen()
                reactor.removeReader(listener)
                httpserver._acceptor._accept()
                reactor.step()
                reactor.step()
                self.assertEqual(1, len(reactor._writers))
                reactor.step()
                self.assertEqual(reactor, suspend._reactor)
                self.assertEqual(0, len(reactor._writers))
                suspend.resume('RESPONSE')
                reactor.step()
                reactor.step()
                reactor.step()
        self.assertEqual([b'before suspend', b'result = RESPONSE', b'after suspend'], listener.data)

    def testSuspendProtocolWithThrow(self):
        suspend = Suspend()
        listener = MyMockSocket()
        port = 9
        def handler(**httpvars):
            yield 'before suspend'
            yield suspend
            try:
                suspend.getResult()
                self.fail()
            except ValueError as e:
                tbstring = format_exc()
                yield "result = %s" % tbstring
            yield 'after suspend'
        with Reactor(select_func=mockselect) as reactor:
            with HttpServer(reactor, port, handler, sok=listener) as httpserver:
                httpserver.listen()
                reactor.removeReader(listener) # avoid new connections
                httpserver._acceptor._accept()
                reactor.step()
                reactor.step()
                self.assertEqual(1, len(reactor._writers))
                reactor.step()
                self.assertEqual(reactor, suspend._reactor)
                self.assertEqual(0, len(reactor._writers))
                def raiser():
                    raise ValueError("BAD VALUE")
                try:
                    raiser()
                except ValueError as e:
                    exc_type, exc_value, exc_traceback = exc_info()
                    suspend.throw(exc_type(exc_value).with_traceback(exc_traceback))
                reactor.step()
                reactor.step()
                reactor.step()
                expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
      File "%(__file__)s", line [#], in handler
        suspend.getResult()
      File "../weightless/io/_suspend.py", line [#], in getResult
        raise self._exception[1].with_traceback(self._exception[2])
    ValueError: BAD VALUE""" % fileDict)
                self.assertEqual(3, len(listener.data))
                self.assertEqual(b'before suspend', listener.data[0])
                #self.assertEqualsWS("result = %s" % expectedTraceback, ignoreLineNumbers(listener.data[1].decode('UTF-8')))
                #self.assertEqual(b'after suspend', listener.data[2])

    def testDoNextErrorReRaisedOnGetResult(self):
        def razor(ignored):
            1/0  # Division by zero exception
        suspend = Suspend(doNext=razor)

        with self.stderr_replaced() as stderr:
            with Reactor(log=StringIO()) as reactor:
                suspend(reactor=reactor, whenDone="not called")
            try:
                suspend.getResult()
            except:
                exc_type, exc_value, exc_traceback = exc_info()

                expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
File "%(__file__)s", line 200, in testDoNextErrorReRaisedOnGetResult
  suspend.getResult()
File "%(suspend.py)s", line 40, in getResult
  raise self._exception[1].with_traceback(self._exception[2])
File "%(suspend.py)s", line 40, in __call__
  self._doNext(self)
File "%(__file__)s", line 196, in razor
  1/0  # Division by zero exception
ZeroDivisionError: division by zero
""" % fileDict)
                self.assertEqual(ZeroDivisionError, exc_type)
                self.assertEqualsWS(expectedTraceback, ignoreLineNumbers(format_exc()))

    def testSuspendThrowBackwardsCompatibleWithInstanceOnlyThrow_YouWillMissTracebackHistory(self):
        suspend = Suspend()
        def handler(**httpvars):
            yield 'before suspend'
            yield suspend
            try:
                suspend.getResult()
                self.fail()
            except ValueError as e:
                tbstring = format_exc()
                yield "result = %s" % tbstring
            yield 'after suspend'
        listener = MyMockSocket()
        port = 9
        with Reactor(select_func=mockselect) as reactor:
            with HttpServer(reactor, port, handler, sok=listener) as httpserver:
                httpserver.listen()
                reactor.removeReader(listener) # avoid new connections
                httpserver._acceptor._accept()
                reactor.step()
                reactor.step()
                self.assertEqual(1, len(reactor._writers))
                reactor.step()
                self.assertEqual(reactor, suspend._reactor)
                self.assertEqual(0, len(reactor._writers))
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
    raise self._exception[1].with_traceback(self._exception[2])
ValueError: BAD VALUE
        """ % fileDict)
                self.assertEqual(3, len(listener.data))
                self.assertEqual(b'before suspend', listener.data[0])
                self.assertEqualsWS("result = %s" % expectedTraceback, ignoreLineNumbers(listener.data[1].decode('UTF-8')))
                self.assertEqual(b'after suspend', listener.data[2])

    def testGetResult(self):
        reactor = CallTrace('reactor')
        s = Suspend()
        s(reactor, whenDone=lambda:None)
        s.resume('state')
        self.assertEqual('state', s.getResult())

    def testGetNoneResult(self):
        reactor = CallTrace('reactor')
        s = Suspend()
        s(reactor, whenDone=lambda:None)
        s.resume()
        self.assertEqual(None, s.getResult())

    def testGetResultRaisesException(self):
        reactor = CallTrace('reactor')
        s = Suspend()
        s(reactor, whenDone=lambda:None)
        s.throw(ValueError('bad value'))
        self.assertRaises(ValueError, s.getResult)

    def testCleanUp(self):
        with Reactor(select_func=mockselect) as reactor:
            def handler():
                reactor.suspend()
                yield
            reactor.addWriter(1, lambda: None)
            reactor.addReader(2, lambda: None)
            reactor.addReader(3, handler().__next__)
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
        return b'GET / HTTP/1.0\r\n\r\n'
    def getpeername(self):
        return b'itsme'
    def shutdown(self, *args):
        pass
    def close(self):
        pass
    def send(self, chunk, flags=None):
        self.data.append(chunk)
        return len(chunk)

def ignoreLineNumbers(s):
    return sub("line \d+,", "line [#],", s)

