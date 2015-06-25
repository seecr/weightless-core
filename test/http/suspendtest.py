## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015 Seecr (Seek You Too B.V.) http://seecr.nl
# Copyright (C) 2015 Koninklijke Bibliotheek (KB) http://www.kb.nl
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

from __future__ import with_statement

import sys
from StringIO import StringIO
from os import tmpfile
from re import sub
from sys import exc_info
from time import sleep
from traceback import format_exc

from seecr.test import CallTrace
from seecr.test.io import stderr_replaced
from seecr.test.portnumbergenerator import PortNumberGenerator

from weightlesstestcase import WeightlessTestCase

from weightless.core import identify, compose, Yield
from weightless.io import Reactor, Suspend, TimeoutException
from weightless.io.utils import asProcess
from weightless.http import HttpServer


class MockSocket(object):
    def __init__(self):
        self._readAndWritable = tmpfile()

    def fileno(self):
        return self._readAndWritable.fileno()

    def close(self):
        self.closed = True
        self._readAndWritable.close()

fileDict = {
    '__file__': MockSocket.fileno.im_func.func_code.co_filename, # Hacky, but sys.modules[aModuleName].__file__ is inconsistent with traceback-filenames
    'suspend.py': Suspend.__call__.func_code.co_filename,
}


class SuspendTest(WeightlessTestCase):
    def testResumeOrThrowOnlyOnce(self):
        # A.k.a. Promise / Future like behaviour.
        trace = CallTrace("Reactor")
        def getSuspend():
            trace.calledMethods.reset()
            suspend = Suspend(doNext=trace.doNext)
            self.assertEquals([], trace.calledMethodNames())

            suspend(reactor=trace, whenDone=trace.whenDone)
            self.assertEquals(['doNext', 'suspend'], trace.calledMethodNames())
            doNextM, suspendM = trace.calledMethods
            self.assertEquals(((suspend,), {}), (doNextM.args, doNextM.kwargs))
            self.assertEquals(((), {}), (suspendM.args, suspendM.kwargs))
            trace.calledMethods.reset()
            return suspend

        suspend = getSuspend()
        suspend.resume(response='whatever')
        self.assertEquals(['whenDone'], trace.calledMethodNames())
        trace.calledMethods.reset()
        # Below no change of result, no side-effects
        self.assertEquals('whatever', suspend.getResult())
        try:
            suspend.resume(response='DIFFERENT')
        except AssertionError, e:
            self.assertEquals('Suspend already settled.', str(e))
        else: self.fail()
        self.assertEquals('whatever', suspend.getResult())
        self.assertRaises(AssertionError, lambda: suspend.throw(exc_type=Exception, exc_value=Exception('Very'), exc_traceback=None))
        self.assertEquals('whatever', suspend.getResult())
        self.assertEquals([], trace.calledMethodNames())

        suspend = getSuspend()
        suspend.throw(RuntimeError, RuntimeError('Very'), None)
        self.assertEquals(['whenDone'], trace.calledMethodNames())
        trace.calledMethods.reset()
        # Below no change of result, no side-effects
        self.assertRaises(RuntimeError, lambda: suspend.getResult())
        self.assertRaises(AssertionError, lambda: suspend.resume(response='whatever'))
        self.assertRaises(RuntimeError, lambda: suspend.getResult())
        self.assertRaises(AssertionError, lambda: suspend.throw(exc_type=Exception, exc_value=Exception('Very'), exc_traceback=None))
        self.assertRaises(RuntimeError, lambda: suspend.getResult())
        self.assertEquals([], trace.calledMethodNames())

    def testReactorSuspend(self):
        handle = ['initial value']
        reactor = Reactor()
        def callback():
            handle[0] = reactor.suspend()
        sok1 = MockSocket()
        reactor.addReader(sok1, callback)
        self.assertTrue(sok1 in reactor._readers)
        reactor.step()
        self.assertTrue(sok1 not in reactor._readers)

        sok2 = MockSocket()
        reactor.addWriter(sok2, callback)
        self.assertTrue(sok2 in reactor._writers)
        reactor.step()
        self.assertTrue(sok2 not in reactor._writers)
        self.assertTrue(handle[0] != None)
        self.assertTrue(handle[0] != 'initial value')

        # cleanup fd's
        sok1.close(); sok2.close()

    def testReactorResumeWriter(self):
        handle = ['initial value']
        reactor = Reactor()
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

        # cleanup fd's
        sok.close()

    def testReactorResumeReader(self):
        handle = ['initial value']
        reactor = Reactor()
        def callback():
            handle[0] = reactor.suspend()
            yield
            yield
        sok = MockSocket()
        reactor.addReader(sok, callback().next)
        reactor.step()
        reactor.resumeReader(handle[0])
        reactor.step()
        self.assertFalse(sok in reactor._writers)
        self.assertTrue(sok in reactor._readers)
        self.assertRaises(KeyError, reactor.resumeReader, handle[0])

        # cleanup fd's
        sok.close()

    def testReactorResumeProcess(self):
        reactor = Reactor()
        def callback():
            handle[0] = reactor.suspend()
            yield
            yield
        handle = [callback().next]
        sok = MockSocket()
        reactor.addProcess(handle[0])
        reactor.step()
        reactor.resumeProcess(handle[0])
        reactor.step()
        self.assertFalse(handle[0] in reactor._writers)
        self.assertFalse(handle[0] in reactor._readers)
        self.assertTrue(handle[0] in reactor._processes)
        self.assertRaises(KeyError, reactor.resumeProcess, handle[0])

        # cleanup fd's
        sok.close()

    def testWrongUseAfterSuspending(self):
        reactor = Reactor()
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

        # cleanup fd's
        sok.close()

    def testShutdownReactor(self):
        reactor = Reactor()
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
        with self.stdout_replaced() as s:
            reactor.shutdown() 
            self.assertTrue(str(sok1) in s.getvalue(), s.getvalue())
            self.assertTrue(str(sok2) in s.getvalue(), s.getvalue())
        self.assertTrue(str(sok3) in s.getvalue())
        self.assertTrue(sok1.closed)
        self.assertTrue(sok2.closed)
        self.assertTrue(sok3.closed)

    def testSuspendProtocol(self):
        reactor = Reactor()
        suspend = Suspend()
        def handler(**httpvars):
            yield 'before suspend'
            yield suspend
            yield "result = %s" % suspend.getResult()
            yield 'after suspend'
        listener = MyMockSocket()
        port = PortNumberGenerator.next()
        httpserver = HttpServer(reactor, port, handler, sok=listener)
        httpserver.listen()
        reactor.removeReader(listener) # avoid new connections
        httpserver._acceptor._accept()
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

        # cleanup (most) fd's
        listener.close()

    def testSuspendProtocolWithThrow(self):
        reactor = Reactor()
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
        port = PortNumberGenerator.next()
        httpserver = HttpServer(reactor, port, handler, sok=listener)
        httpserver.listen()
        reactor.removeReader(listener) # avoid new connections
        httpserver._acceptor._accept()
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

        # cleanup (most) fd's
        listener.close()

    def testSuspendTimingOut(self):
        # with calltrace; happy path
        trace = CallTrace(returnValues={'addTimer': 'timerToken'})
        suspend = Suspend(doNext=trace.doNext, timeout=3.14, onTimeout=trace.onTimeout)
        self.assertEquals([], trace.calledMethodNames())
        self.assertEquals(None, suspend._timer)

        suspend(reactor=trace, whenDone=trace.whenDone)
        self.assertEquals(['doNext', 'addTimer', 'suspend'], trace.calledMethodNames())
        doNextM, addTimerM, suspendM = trace.calledMethods
        self.assertEquals(((suspend,), {}), (doNextM.args, doNextM.kwargs))
        self.assertEquals(((), {'seconds': 3.14, 'callback': suspend._timedOut}), (addTimerM.args, addTimerM.kwargs))
        self.assertEquals(((), {}), (suspendM.args, suspendM.kwargs))
        self.assertEquals('timerToken', suspend._timer)

        trace.calledMethods.reset()
        suspend._timedOut()
        self.assertEquals(['onTimeout', 'whenDone'], trace.calledMethodNames())
        onTimeoutM, whenDoneM = trace.calledMethods
        self.assertEquals(((), {}), (onTimeoutM.args, onTimeoutM.kwargs))
        self.assertEquals(((), {}), (whenDoneM.args, whenDoneM.kwargs))
        self.assertEquals(None, suspend._timer)

        self.assertRaises(TimeoutException, lambda: suspend.getResult())

    def testSuspendTimeoutSettlesSuspend(self):
        def prepare():
            trace = CallTrace(returnValues={'addTimer': 'timerToken'})
            suspend = Suspend(doNext=trace.doNext, timeout=3.14, onTimeout=trace.onTimeout)
            suspend(reactor=trace, whenDone=trace.whenDone)
            self.assertEquals(['doNext', 'addTimer', 'suspend'], trace.calledMethodNames())

            trace.calledMethods.reset()
            suspend._timedOut()
            self.assertEquals(['onTimeout', 'whenDone'], trace.calledMethodNames())
            self.assertEquals(True, suspend._settled)
            trace.calledMethods.reset()
            return trace, suspend

        # basic invariant
        trace, suspend = prepare()
        self.assertRaises(TimeoutException, lambda: suspend.getResult())

        # resume on settled is a no-op
        trace, suspend = prepare()
        self.assertRaises(AssertionError, lambda: suspend.resume('whatever'))
        self.assertEquals([], trace.calledMethodNames())
        self.assertRaises(TimeoutException, lambda: suspend.getResult())

        # throw on settled is a no-op
        trace, suspend = prepare()
        self.assertRaises(AssertionError, lambda: suspend.throw(RuntimeError, RuntimeError('R'), None))
        self.assertEquals([], trace.calledMethodNames())
        self.assertRaises(TimeoutException, lambda: suspend.getResult())

    def testSuspendCouldTimeoutButDidNot(self):
        # with calltrace
        def prepare():
            trace = CallTrace(returnValues={'addTimer': 'timerToken'})
            suspend = Suspend(doNext=trace.doNext, timeout=3.14, onTimeout=trace.onTimeout)
            self.assertEquals([], trace.calledMethodNames())

            suspend(reactor=trace, whenDone=trace.whenDone)
            self.assertEquals(['doNext', 'addTimer', 'suspend'], trace.calledMethodNames())
            doNextM, addTimerM, suspendM = trace.calledMethods
            self.assertEquals(((suspend,), {}), (doNextM.args, doNextM.kwargs))
            self.assertEquals(((), {'seconds': 3.14, 'callback': suspend._timedOut}), (addTimerM.args, addTimerM.kwargs))
            self.assertEquals(((), {}), (suspendM.args, suspendM.kwargs))

            trace.calledMethods.reset()
            return trace, suspend

        # with resume
        trace, suspend = prepare()
        suspend.resume('retval')
        self.assertEquals(['removeTimer', 'whenDone'], trace.calledMethodNames())
        removeTimerM, whenDoneM = trace.calledMethods
        self.assertEquals(((), {'token': 'timerToken'}), (removeTimerM.args, removeTimerM.kwargs))
        self.assertEquals(((), {}), (whenDoneM.args, whenDoneM.kwargs))

        self.assertEquals('retval', suspend.getResult())

        # with throw
        trace, suspend = prepare()
        suspend.throw(RuntimeError, RuntimeError('R'), None)
        self.assertEquals(['removeTimer', 'whenDone'], trace.calledMethodNames())
        removeTimerM, whenDoneM = trace.calledMethods
        self.assertEquals(((), {'token': 'timerToken'}), (removeTimerM.args, removeTimerM.kwargs))
        self.assertEquals(((), {}), (whenDoneM.args, whenDoneM.kwargs))

        self.assertRaises(RuntimeError, lambda: suspend.getResult())

    def testSuspendTimeoutOnTimeoutCallbackGivesException(self):
        def prepare(_onTimeout):
            # Use indirect tracing of onTimeout call (otherwise CallTrace internals leak into the stacktrace).
            trace = CallTrace(returnValues={'addTimer': 'timerToken'})
            onTimeoutM = trace.onTimeout
            def onTimeoutTraced():
                onTimeoutM()  # We have been called Watson!
                return _onTimeout()
            trace.onTimeout = onTimeoutTraced

            suspend = Suspend(doNext=trace.doNext, timeout=3.14, onTimeout=trace.onTimeout)
            suspend(reactor=trace, whenDone=trace.whenDone)
            self.assertEquals(['doNext', 'addTimer', 'suspend'], trace.calledMethodNames())
            trace.calledMethods.reset()
            return trace, suspend

        # basic invariant
        trace, suspend = prepare(lambda: None)
        suspend._timedOut()
        self.assertEquals(['onTimeout', 'whenDone'], trace.calledMethodNames())
        self.assertRaises(TimeoutException, lambda: suspend.getResult())

        # normal exceptions
        def onTimeout():
            raise Exception("This Should Never Happen But Don't Expose Exception If It Does Anyway !")
        trace, suspend = prepare(onTimeout)
        with stderr_replaced() as err:
            suspend._timedOut()
            expectedTraceback = ignoreLineNumbers('''Unexpected exception raised on Suspend's onTimeout callback (ignored):
Traceback (most recent call last):
  File "%(suspend.py)s", line 101, in _timedOut
    self._onTimeout()
  File "%(__file__)s", line 382, in onTimeoutTraced
    return _onTimeout()
  File "%(__file__)s", line 398, in onTimeout
    raise Exception("This Should Never Happen But Don't Expose Exception If It Does Anyway !")
Exception: This Should Never Happen But Don't Expose Exception If It Does Anyway !
                ''' % fileDict)
            self.assertEqualsWS(expectedTraceback, ignoreLineNumbers(err.getvalue()))
        self.assertEquals(['onTimeout', 'whenDone'], trace.calledMethodNames())
        self.assertRaises(TimeoutException, lambda: suspend.getResult())

        # fatal exceptions
        def suspendCallWithOnTimeoutRaising(exception):
            def onTimeout():
                raise exception
            trace, suspend = prepare(onTimeout)
            try:
                suspend._timedOut()
            except:
                c, v, t = exc_info()
                self.assertEquals(['onTimeout'], trace.calledMethodNames())
                raise c, v, t.tb_next

        self.assertRaises(KeyboardInterrupt, lambda: suspendCallWithOnTimeoutRaising(KeyboardInterrupt()))
        self.assertRaises(SystemExit, lambda: suspendCallWithOnTimeoutRaising(SystemExit()))
        self.assertRaises(AssertionError, lambda: suspendCallWithOnTimeoutRaising(AssertionError()))

    def testSuspendTimeoutArguments(self):
        self.assertRaises(ValueError, lambda: Suspend(timeout=3))
        self.assertRaises(ValueError, lambda: Suspend(onTimeout=lambda: None))
        Suspend()
        Suspend(timeout=3, onTimeout=lambda: None)

    def testSuspendTimingProtocol(self):
        # happy path for timing out and not timing out
        def test(expectTimeout):
            count = []
            timedOut = []
            @identify
            def workInSuspendGenF():
                this = yield
                suspend = yield
                suspend._reactor.addProcess(process=this.next)
                try:
                    for i in xrange(5):
                        count.append(True)
                        yield
                    while True:
                        sleep(0.0001)
                        if not expectTimeout:
                            break
                        yield
                    suspend.resume('retval')
                except TimeoutException:
                    timedOut.append(True)
                finally:
                    suspend._reactor.removeProcess(process=this.next)
                yield  # Wait for GC

            def workInSuspend():
                g = workInSuspendGenF()
                def doNext(suspend):
                    g.send(suspend)
                def onTimeout():
                    g.throw(TimeoutException, TimeoutException(), None)
                return doNext, onTimeout

            def suspendWrap():
                doNext, onTimeout = workInSuspend()
                s = Suspend(doNext=doNext, timeout=0.01, onTimeout=onTimeout)
                yield s
                result = s.getResult()
                if expectTimeout:
                    self.fail('Should not have come here')
                raise StopIteration(result)

            try:
                result = yield suspendWrap()
                if expectTimeout:
                    self.fail()
            except TimeoutException:
                self.assertEquals(5, len(count))
                self.assertEquals(expectTimeout, bool(timedOut))

            if not expectTimeout:
                self.assertEquals('retval', result)

            testRun.append(True)

        # Simple driver - timing out
        testRun = []
        asProcess(test(expectTimeout=True))
        self.assertEquals(True, bool(testRun))

        # Simple driver - not timing out
        del testRun[:]
        asProcess(test(expectTimeout=False))
        self.assertEquals(True, bool(testRun))

        # http server - timing out
        self.reactor = Reactor()
        del testRun[:]
        port = PortNumberGenerator.next()
        def reqHandler(**whatever):
            def inner():
                yield test(expectTimeout=True)
                yield 'HTTP/1.0 200 OK\r\n\r\n'
            return compose(inner())
        servert = HttpServer(reactor=self.reactor, port=port, generatorFactory=reqHandler, bindAddress='127.42.42.42')

        servert.listen()
        with self.loopingReactor():
            sok = self.httpGet(host='127.42.42.42', port=port, path='/ignored')
            allData = ''
            try:
                while allData != 'HTTP/1.0 200 OK\r\n\r\n':
                    allData += sok.recv(4096)
            finally:
                servert.shutdown()
        self.assertEquals(True, bool(testRun))

        # http server - not timing out
        self.reactor = Reactor()
        del testRun[:]
        port = PortNumberGenerator.next()
        def reqHandler(**whatever):
            def inner():
                yield test(expectTimeout=False)
                yield 'HTTP/1.0 200 OK\r\n\r\n'
            return compose(inner())
        servert = HttpServer(reactor=self.reactor, port=port, generatorFactory=reqHandler, bindAddress='127.42.42.42')

        servert.listen()
        with self.loopingReactor():
            sok = self.httpGet(host='127.42.42.42', port=port, path='/ignored')
            allData = ''
            try:
                while allData != 'HTTP/1.0 200 OK\r\n\r\n':
                    allData += sok.recv(4096)
            finally:
                servert.shutdown()
        self.assertEquals(True, bool(testRun))

    def testDoNextErrorReRaisedOnGetResult(self):
        def razor(ignored):
            1/0  # Division by zero exception
        suspend = Suspend(doNext=razor)
        olderr = sys.stderr
        sys.stderr = StringIO()
        try:
            suspend(reactor=CallTrace(), whenDone="not called")
        finally:
            sys.stderr = olderr
        try:
            suspend.getResult()
        except:
            exc_type, exc_value, exc_traceback = exc_info()


        expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
  File "%(__file__)s", line 200, in testDoNextErrorReRaisedOnGetResult
    suspend.getResult()
  File "%(suspend.py)s", line 40, in __call__
    self._doNext(self)
  File "%(__file__)s", line 196, in razor
    1/0  # Division by zero exception
ZeroDivisionError: integer division or modulo by zero
        """ % fileDict)
        self.assertEquals(ZeroDivisionError, exc_type)
        self.assertEqualsWS(expectedTraceback, ignoreLineNumbers(format_exc(exc_traceback)))

    def testDoNextThrowsImmediatelyOnFatalExceptions(self):
        def suspendWithDoNextException(exception):
            def doNextRaising(suspend):
                raise exception
            suspend = Suspend(doNext=doNextRaising)
            suspend(reactor=CallTrace(), whenDone="not called")

        self.assertRaises(KeyboardInterrupt, lambda: suspendWithDoNextException(KeyboardInterrupt('err')))
        self.assertRaises(SystemExit, lambda: suspendWithDoNextException(SystemExit('err')))
        self.assertRaises(AssertionError, lambda: suspendWithDoNextException(AssertionError('err')))

    def testSuspendThrowBackwardsCompatibleWithInstanceOnlyThrow_YouWillMissTracebackHistory(self):
        reactor = Reactor()
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
        port = PortNumberGenerator.next()
        httpserver = HttpServer(reactor, port, handler, sok=listener)
        httpserver.listen()
        reactor.removeReader(listener) # avoid new connections
        httpserver._acceptor._accept()
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
    raise self._exception[0], self._exception[1], self._exception[2] 
ValueError: BAD VALUE
        """ % fileDict)
        self.assertEquals(3, len(listener.data))
        self.assertEquals('before suspend', listener.data[0])
        self.assertEqualsWS("result = %s" % expectedTraceback, ignoreLineNumbers(listener.data[1]))
        self.assertEquals('after suspend', listener.data[2])

        # cleanup (most) fd's
        listener.close()

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
        reactor = Reactor()
        def handler():
            reactor.suspend()
            yield
        one = MockSocket()
        two = MockSocket()
        three = MockSocket()
        reactor.addWriter(one, lambda: None)
        reactor.addReader(two, lambda: None)
        reactor.addReader(three, handler().next)
        reactor.step()
        self.assertTrue(one in reactor._writers)
        reactor.cleanup(one)
        self.assertFalse(one in reactor._writers)
        self.assertTrue(two in reactor._readers)
        reactor.cleanup(two)
        self.assertFalse(two in reactor._readers)
        self.assertTrue(three in reactor._suspended)
        reactor.cleanup(three)
        self.assertFalse(three in reactor._suspended)


class MyMockSocket(object):
    def __init__(self, data=None):
        self._readAndWritable = tmpfile()
        self.data = [] if data is None else data

    def fileno(self):
        return self._readAndWritable.fileno()

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
        self._readAndWritable.close()

    def send(self, chunk, options):
        self.data.append(chunk)
        return len(chunk)


def ignoreLineNumbers(s):
    return sub("line \d+,", "line [#],", s)

