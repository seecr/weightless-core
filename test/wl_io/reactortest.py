## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2015 Seecr (Seek You Too B.V.) http://seecr.nl
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

#
from __future__ import with_statement

from weightlesstestcase import WeightlessTestCase

import os, sys
from StringIO import StringIO
from select import error as ioerror, select
from signal import signal, SIGALRM, alarm
from socket import socketpair, error, socket
from tempfile import mkstemp
from threading import Thread
from time import time, sleep

from weightless.core.utils import identify
from weightless.io import Reactor, reactor
from weightless.io.utils import asProcess


class ReactorTest(WeightlessTestCase):

    def testAddSocketReading(self):
        class Sok:
            def __hash__(self): return 1
        reactor = Reactor()
        mockSok = Sok()
        self.assertTrue(mockSok not in reactor._readers)
        reactor.addReader(mockSok, lambda: None)
        self.assertTrue(mockSok in reactor._readers)
        reactor.removeReader(mockSok)
        self.assertFalse(mockSok in reactor._readers)

    def testAddSocketWriting(self):
        class Sok:
            def __hash__(self): return 1
        reactor = Reactor()
        mockSok = Sok()
        self.assertTrue(mockSok not in reactor._writers)
        reactor.addWriter(mockSok, None)
        self.assertTrue(mockSok in reactor._writers)
        reactor.removeWriter(mockSok)
        self.assertFalse(mockSok in reactor._writers)

    def testAddSocketRaisesException(self):
        class Sok: # raise exception when put into set
            def __hash__(self): raise Exception('aap')
        reactor = Reactor()
        try:
            reactor.addReader(Sok(), None)
            self.fail()
        except Exception, e:
            self.assertEquals('aap', str(e))

    def testReadFile(self):
        reactor = Reactor()
        fd, path = mkstemp()
        os.write(fd, 'some data')
        os.close(fd)
        try:
            f = open(path)
            def readable():
                self.readable = True
            reactor.addReader(f, readable)
            reactor.step()
            self.assertTrue(self.readable)
        finally:
            f.close()
            os.remove(path)

    def testTimer(self):
        reactor = Reactor()
        def itsTime():
            itstime.append(True)
        reactor.addTimer(0.05, itsTime)
        reactor.addTimer(0.5, itsTime)
        reactor.addTimer(0.25, itsTime)
        start = time()
        itstime = []
        while not itstime:
            reactor.step()
        self.assertTrue(0.04 < time() - start < 0.06, time() - start)
        itstime = []
        while not itstime:
            reactor.step()
        self.assertTrue(0.20 < time() - start < 0.30, time()-start)
        itstime = []
        while not itstime:
            reactor.step()
        self.assertTrue(0.45 < time() - start < 0.55, time()-start)
        itstime = []

    def testMustRemoveToBeExecutedTimerNotTheFirstOne(self):
        reactor = Reactor()
        executed = []
        def addNewTimer():
            reactor.addTimer(0.001, lambda: executed.append('newTimer'))
            sleep(0.15)
        reactor.addTimer(0, lambda: (addNewTimer(), executed.append('zero')))
        reactor.addTimer(0.1, lambda: executed.append('one'))

        reactor.step()
        reactor.step()
        self.assertEquals(0, len(reactor._timers))
        self.assertEquals(['zero', 'newTimer', 'one'], executed)

    def testInvalidTime(self):
        reactor = Reactor()
        try:
            reactor.addTimer(-1, None)
            self.fail('should raise exeption')
        except Exception, e:
            self.assertEquals('Timeout must be >= 0. It was -1.', str(e))

    def testDuplicateTimerDoesNotCauseZeroTimeout(self):
        itstime = []
        def itsTime():
            itstime.append(True)
        reactor = Reactor()
        reactor.addTimer(0.05, itsTime)
        reactor.addTimer(0.05, itsTime)
        reactor.addTimer(0.05, itsTime)
        reactor.addTimer(0.05, itsTime)
        reactor.addTimer(0.05, itsTime)
        while itstime != [True, True, True, True, True]:
            reactor.step()
        self.assertEquals([True, True, True, True, True], itstime)

    def testRemoveTimer(self):
        def itsTime(): pass
        reactor = Reactor()
        token1 = reactor.addTimer(0.05, itsTime)
        token2 = reactor.addTimer(0.051, itsTime)
        reactor.removeTimer(token1)
        self.assertEquals(1, len(reactor._timers))

    def testRemoveTimerById(self):
        def itsTime(): pass
        reactor = Reactor()
        token1 = reactor.addTimer(0.051, itsTime)
        token2 = reactor.addTimer(0.051, itsTime)
        token3 = reactor.addTimer(0.051, itsTime)
        token3.time = token2.time = token1.time  # whiteboxing, can happen in real code, not easy to reproduce in a test situation.
        self.assertEquals(token1.callback, token2.callback)
        self.assertEquals(token2.callback, token3.callback)
        reactor.removeTimer(token2)
        self.assertEquals([token1, token3], reactor._timers)

    def testRemoveTimerWithSameTimestamp(self):
        reactor = Reactor()
        token1 = reactor.addTimer(1, lambda: None)
        token2 = reactor.addTimer(1, lambda: None)
        token2.time = token1.time

        reactor.removeTimer(token2)
        self.assertEquals([id(token1)], [id(t) for t in reactor._timers])
        reactor.removeTimer(token1)
        self.assertEquals([], reactor._timers)

    def testRemoveEffectiveImmediately(self):
        readAndWritable = lambda: os.tmpfile()

        log = []
        processDone = []
        @identify
        def run():
            del log[:]
            del processDone[:]
            this = yield
            yield  # wait for reactor
            _reactor = reactor()
            one, two = eitherOr(), eitherOr()
            one.send(two); two.send(one)
            token = _reactor.addTimer(seconds=1, callback=lambda: self.fail('hangs'))
            while len(processDone) != 2:
                yield

            _reactor.removeTimer(token=token)
            processDone.append(True)

        # process removing process
        @identify
        def eitherOr():
            this = yield
            other = yield
            _reactor = reactor()
            _reactor.addProcess(process=this.next)
            try:
                yield  # Wait for reactor's step
                other.throw(Exception, Exception('Stop Please'), None)  # I'll do the work, other should not bother.
                log.append('work')
            except Exception, e:
                self.assertEquals('Stop Please', str(e))
                log.append('abort')
            _reactor.removeProcess(process=this.next)
            processDone.append(True)
            yield  # wait for GC
            self.fail('Called After Remove!')

        asProcess(run())
        self.assertEquals(['abort', 'work'], log)
        self.assertEquals(3, len(processDone))

        # reader removing reader
        @identify
        def eitherOr():
            this = yield
            other = yield
            _reactor = reactor()
            rw = readAndWritable()
            _reactor.addReader(sok=rw, sink=this.next)
            try:
                yield  # Wait for reactor's step
                other.throw(Exception, Exception('Stop Please'), None)  # I'll do the work, other should not bother.
                log.append('work')
            except Exception, e:
                self.assertEquals('Stop Please', str(e))
                log.append('abort')
            _reactor.removeReader(sok=rw)
            processDone.append(True)
            yield  # wait for GC
            self.fail('Called Twice!')

        asProcess(run())
        self.assertEquals(['abort', 'work'], log)
        self.assertEquals(3, len(processDone))

        # writer removing writer
        @identify
        def eitherOr():
            this = yield
            other = yield
            _reactor = reactor()
            rw = readAndWritable()
            _reactor.addWriter(sok=rw, source=this.next)
            try:
                yield  # Wait for reactor's step
                other.throw(Exception, Exception('Stop Please'), None)  # I'll do the work, other should not bother.
                log.append('work')
            except Exception, e:
                self.assertEquals('Stop Please', str(e))
                log.append('abort')
            _reactor.removeWriter(sok=rw)
            processDone.append(True)
            yield  # wait for GC
            self.fail('Called Twice!')

        asProcess(run())
        self.assertEquals(['abort', 'work'], log)
        self.assertEquals(3, len(processDone))

        # timer removing timer
        @identify
        def eitherOr():
            this = yield
            other = yield
            _reactor = reactor()
            token = _reactor.addTimer(seconds=0, callback=this.next)
            try:
                yield  # Wait for reactor's step
                other.throw(Exception, Exception('Stop Please'), None)  # I'll do the work, other should not bother.
                log.append('work')
            except Exception, e:
                self.assertEquals('Stop Please', str(e))
                _reactor.removeTimer(token=token)
                log.append('abort')
            processDone.append(True)
            yield  # wait for GC
            self.fail('Called Twice!')

        asProcess(run())
        self.assertEquals(['abort', 'work'], log)
        self.assertEquals(3, len(processDone))

    def testExceptionInTimeoutCallback(self):
        sys.stderr = StringIO()
        try:
            def itsTime(): raise Exception('here is the exception')
            reactor = Reactor()
            token1 = reactor.addTimer(0.001, itsTime)
            try:
                reactor.step()
            except:
                self.fail('must not raise exception')
        finally:
            sys.stderr = sys.__stderr__

    def testSelfModifyingLoopSkipsEverySecondTimerAndDeletesTheWrongOneBUG(self):
        done = []
        reactor = Reactor()
        def callback1():
            self.assertEquals([], done)
            done.append(1)
            self.assertEquals([timer2, timer3], reactor._timers)
        def callback2():
            self.assertEquals([1], done)
            done.append(2)
            self.assertEquals([timer3], reactor._timers)
        def callback3():
            self.assertEquals([1,2], done)
            done.append(3)
            self.assertEquals([], reactor._timers)
        timer1 = reactor.addTimer(0.0001, callback1)
        timer2 = reactor.addTimer(0.0002, callback2)
        timer3 = reactor.addTimer(0.0003, callback3)
        self.assertEquals([timer1, timer2, timer3], reactor._timers)
        sleep(0.04)
        reactor.step()
        self.assertEquals([1,2,3], done)
        self.assertEquals([], reactor._timers)

    def testAssertionErrorInReadCallback(self):
        sys.stderr = StringIO()
        try:
            def callback(): raise AssertionError('here is the assertion')
            reactor = Reactor(lambda r, w, o, t: (r,w,o))
            reactor.addReader(9, callback)
            try:
                reactor.step()
                self.fail('must raise exception')
            except AssertionError, e:
                self.assertEquals('here is the assertion', str(e))
        finally:
            sys.stderr = sys.__stderr__

    def testAssertionErrorInWRITECallback(self):
        sys.stderr = StringIO()
        try:
            def callback(): raise AssertionError('here is the assertion')
            reactor = Reactor(lambda r, w, o, t: (r,w,o))
            reactor.addWriter(9, callback)
            try:
                reactor.step()
                self.fail('must raise exception')
            except AssertionError, e:
                self.assertEquals('here is the assertion', str(e))
        finally:
            sys.stderr = sys.__stderr__

    def testWriteFollowsRead(self):
        reactor = Reactor(lambda r,w,o,t: (r,w,o))
        t = []
        def read():
            t.append('t1')
        def write():
            t.append('t2')
        reactor.addWriter('sok1', write)
        reactor.addReader('sok1', read)
        reactor.step()
        self.assertEquals(['t1', 't2'], t)

    def testReadDeletesWrite(self):
        reactor = Reactor(lambda r,w,o,t: (r,w,o))
        self.read = self.write = False
        def read():
            self.read = True
            reactor.removeWriter('sok1')
        def write():
            self.write = True
        reactor.addWriter('sok1', write)
        reactor.addReader('sok1', read)
        reactor.step()
        self.assertTrue(self.read)
        self.assertFalse(self.write)

    def testReadFollowsTimer(self):
        reactor = Reactor(lambda r,w,o,t: (r,w,o))
        t = []
        def timer():
            t.append('t1')
        def read():
            t.append('t2')
        reactor.addTimer(0, timer)
        reactor.addReader('sok1', read)
        reactor.step()
        self.assertEquals(['t1', 't2'], t)

    def testTimerDeletesRead(self):
        reactor = Reactor(lambda r,w,o,t: (r,w,o))
        self.read = self.timer = False
        def read():
            self.read = True
        def timer():
            self.timer = True
            reactor.removeReader('sok1')
        reactor.addTimer(0, timer)
        reactor.addReader('sok1', read)
        reactor.step()
        self.assertTrue(self.timer)
        self.assertFalse(self.read)

    def testInterruptedSelectDoesNotDisturbTimer(self):
        reactor = Reactor()
        self.time = False
        def signalHandler(signum, frame):
            self.alarm = True
        def timeout():
            self.time = time()
        signal(SIGALRM, signalHandler)
        targetTime = time() + 1.1
        reactor.addTimer(1.1, timeout)
        alarm(1) # alarm only accept ints....
        try:
            with self.stderr_replaced() as s:
                while not self.time:
                    reactor.step()
                self.assertTrue("4, 'Interrupted system call'" in s.getvalue(), s.getvalue())
            self.assertTrue(self.alarm)
            self.assertTrue(targetTime - 0.01 < self.time, targetTime + 0.01)
        except ioerror:
            self.fail('must not fail on Interrupted system call')

    def testGetRidOfBadFileDescriptors(self):
        reactor = Reactor()
        class BadSocket(object):
            def fileno(self): return 188
            def close(self): raise Exception('hell breaks loose')
        self.timeout = False
        def timeout():
            self.timeout = True
        reactor.addReader(199, lambda: None) # broken
        reactor.addWriter(199, lambda: None) # broken
        reactor.addReader(BadSocket(), lambda: None) # even more broken
        reactor.addTimer(0.01, timeout)
        with self.stderr_replaced() as s:
            for i in range(10):
                if self.timeout:
                    break
                reactor.step()
            self.assertTrue("Bad file descriptor" in s.getvalue(), s.getvalue())
        self.assertTrue(self.timeout)
        self.assertEquals({}, reactor._readers)
        self.assertEquals({}, reactor._writers)
        self.assertEquals([], reactor._timers)

    def testGetRidOfClosedSocket(self):
        reactor = Reactor()
        sok = socket()
        sok.close()
        callbacks = []
        def callback():
            callbacks.append(True)
        reactor.addReader(sok, callback)
        reactor.addWriter(sok, callback)
        with self.stderr_replaced() as s:
            reactor.step()
            reactor.step()
            self.assertTrue("Bad file descriptor" in s.getvalue(), s.getvalue())
        self.assertEquals({}, reactor._readers)
        self.assertEquals([True, True], callbacks)

    def testDoNotDieButLogOnProgrammingErrors(self):
        reactor = Reactor()
        reactor.addReader('not a sok', lambda: None)
        try:
            sys.stderr = StringIO()
            reactor.step()
            sys.stderr.seek(0)
            self.assertTrue('TypeError: argument must be an int' in sys.stderr.getvalue())
            sys.stderr = sys.__stderr__
        except TypeError:
            self.fail('must not fail')

    def testDoNotMaskOtherErrors(self):
        def raiser(*args): raise Exception('oops')
        reactor = Reactor(raiser)
        try:
            reactor.step()
            self.fail('must raise oops')
        except Exception, e:
            self.assertEquals('oops', str(e))

    def testTimerDoesNotMaskAssertionErrors(self):
        reactor = Reactor()
        reactor.addTimer(0, lambda: self.fail("Assertion Error"))
        try:
            reactor.step()
            raise Exception('step() must raise AssertionError')
        except AssertionError:
            self.assertEquals([], reactor._timers)

    def testTimerDoesNotMaskKeyboardInterrupt(self):
        reactor = Reactor()
        def raiser():
            raise KeyboardInterrupt('Ctrl-C')
        reactor.addTimer(0, raiser)
        try:
            reactor.step()
            self.fail('step() must raise KeyboardInterrupt')
        except KeyboardInterrupt:
            self.assertEquals([], reactor._timers)

    def testTimerDoesNotMaskSystemExit(self):
        reactor = Reactor()
        def raiser():
            raise SystemExit('shutdown...')
        reactor.addTimer(0, raiser)
        try:
            reactor.step()
            self.fail('step() must raise SystemExit')
        except SystemExit:
            self.assertEquals([], reactor._timers)

    def testReaderOrWriterDoesNotMaskKeyboardInterrupt(self):
        fd, path = mkstemp()
        reactor = Reactor()
        def raiser():
            raise KeyboardInterrupt('Ctrl-C')
        reactor.addReader(sok=fd, sink=raiser)
        self.assertEquals([raiser], [c.callback for c in reactor._readers.values()])
        try:
            reactor.step()
            self.fail('step() must raise KeyboardInterrupt')
        except KeyboardInterrupt:
            self.assertEquals([], [c.callback for c in reactor._readers.values()])

        fd, path = mkstemp()
        reactor = Reactor()
        reactor.addWriter(sok=fd, source=raiser)
        try:
            reactor.step()
            self.fail('step() must raise KeyboardInterrupt')
        except KeyboardInterrupt:
            self.assertEquals([], [c.callback for c in reactor._readers.values()])

    def testReaderOrWriterDoesNotMaskSystemExit(self):
        fd, path = mkstemp()
        reactor = Reactor()
        def raiser():
            raise SystemExit('shutdown...')
        reactor.addReader(sok=fd, sink=raiser)
        self.assertEquals([raiser], [c.callback for c in reactor._readers.values()])
        try:
            reactor.step()
            self.fail('step() must raise SystemExit')
        except SystemExit:
            self.assertEquals([], [c.callback for c in reactor._readers.values()])

        fd, path = mkstemp()
        reactor = Reactor()
        reactor.addWriter(sok=fd, source=raiser)
        try:
            reactor.step()
            self.fail('step() must raise SystemExit')
        except SystemExit:
            self.assertEquals([], [c.callback for c in reactor._readers.values()])

    def testGlobalReactor(self):
        from weightless.io import reactor
        thereactor = Reactor()
        def handler():
            self.assertEquals(thereactor, reactor())
        thereactor.addTimer(0, handler)
        thereactor.step()

    def testReadPriorities(self):
        reactor = Reactor()
        local0, remote0 = socketpair()
        local1, remote1 = socketpair()
        data0 = []
        def remoteHandler0():
            data0.append(remote0.recv(999))
        data1 = []
        def remoteHandler1():
            data1.append(remote1.recv(999))
        reactor.addReader(remote0, remoteHandler0, 0)
        reactor.addReader(remote1, remoteHandler1, 2)
        local0.send('ape')
        local1.send('nut')
        reactor.step() #0
        self.assertEquals(['ape'], data0)
        self.assertEquals([], data1)
        reactor.step() #1
        self.assertEquals([], data1)
        reactor.step() #2
        self.assertEquals(['nut'], data1)

    def testMinandMaxPrio(self):
        reactor = Reactor()
        try:
            reactor.addReader('', '', -1)
            self.fail()
        except ValueError, e:
            self.assertEquals('Invalid priority: -1', str(e))
        try:
            reactor.addReader('', '', Reactor.MAXPRIO)
            self.fail()
        except ValueError, e:
            self.assertEquals('Invalid priority: 10', str(e))
        try:
            reactor.addWriter('', '', -1)
            self.fail()
        except ValueError, e:
            self.assertEquals('Invalid priority: -1', str(e))
        try:
            reactor.addWriter('', '', Reactor.MAXPRIO)
            self.fail()
        except ValueError, e:
            self.assertEquals('Invalid priority: 10', str(e))

    def testDefaultPrio(self):
        reactor = Reactor()
        reactor.addReader('', '')
        self.assertEquals(Reactor.DEFAULTPRIO, reactor._readers[''].prio)
        reactor.addWriter('', '')
        self.assertEquals(Reactor.DEFAULTPRIO, reactor._writers[''].prio)

    def testWritePrio(self):
        reactor = Reactor()
        local0, remote0 = socketpair()
        local1, remote1 = socketpair()
        local1.setblocking(0)
        def remoteHandler0():
            remote0.send('ape')
        def remoteHandler1():
            remote1.send('nut')
        reactor.addWriter(remote0, remoteHandler0, 0)
        reactor.addWriter(remote1, remoteHandler1, 2)
        reactor.step() #0
        self.assertEquals('ape', local0.recv(999))
        try:
            local1.recv(999)
            self.fail('must be no data on the socket yet')
        except error:
            pass
        reactor.step() #1
        try:
            local1.recv(999)
            self.fail('must be no data on the socket yet')
        except error:
            pass
        reactor.step() #2
        self.assertEquals('nut', local1.recv(999))

    def testGetOpenConnections(self):
        reactor = Reactor()
        self.assertEquals(0, reactor.getOpenConnections())
        reactor.addReader('', '')
        self.assertEquals(1, reactor.getOpenConnections())
        reactor.addWriter('', '')
        self.assertEquals(2, reactor.getOpenConnections())

        reactor.removeReader('')
        self.assertEquals(1, reactor.getOpenConnections())
        reactor.removeWriter('')
        self.assertEquals(0, reactor.getOpenConnections())

    def testAddProcessGenerator(self):
        reactor = Reactor()
        trace = []
        @identify
        def p():
            this = yield
            yield  # wait after this
            trace.append(1)
            yield
            trace.append(2)
            reactor.removeProcess(this.next)
            yield
            trace.append('should_not_happen')
            yield

        reactor.addProcess(p().next)
        reactor.step()
        self.assertEquals([1], trace)
        reactor.step()
        self.assertEquals([1, 2], trace)

        reactor.addProcess(lambda: None)
        reactor.step()
        self.assertEquals([1, 2], trace)

    def testAddProcessFunction(self):
        reactor = Reactor()
        trace = []
        processMe = [1, 2]
        def p():
            try:
                result = processMe.pop(0) * 2
                trace.append(result)
            except IndexError:
                reactor.removeProcess()
                trace.append('removedProcess')

        reactor.addProcess(p)
        reactor.step()
        self.assertEquals([2], trace)
        reactor.step()
        self.assertEquals([2, 4], trace)
        reactor.step()
        self.assertEquals([2, 4, 'removedProcess'], trace)

        reactor.addProcess(lambda: None)
        reactor.step()
        self.assertEquals([2, 4, 'removedProcess'], trace)

    def testAddProcessSanityCheck(self):
        reactor = Reactor()
        try:
            reactor.addProcess(lambda: None, prio=10)
            self.fail('Should not come here.')
        except ValueError, e:
            self.assertEquals('Invalid priority: 10', str(e))

        try:
            reactor.addProcess(lambda: None, prio=-1)
            self.fail('Should not come here.')
        except ValueError, e:
            self.assertEquals('Invalid priority: -1', str(e))

        lambdaFunc = lambda: reactor.suspend()
        reactor.addProcess(lambdaFunc)
        reactor.step()
        try:
            reactor.addProcess(lambdaFunc)
            self.fail('Should not come here.')
        except ValueError, e:
            self.assertEquals('Process is suspended', str(e))

    def testProcessAddsNotWhenAlreadyInThere(self):
        reactor = Reactor()
        aProcess = lambda: None
        reactor.addProcess(aProcess)
        try:
            reactor.addProcess(aProcess)
            self.fail('Should not come here.')
        except ValueError, e:
            self.assertEquals('Process is already in processes', str(e))

    def testProcessPriority(self):
        reactor = Reactor()
        trace = []

        defaultPass = iter(xrange(99))
        def defaultPrio():
            trace.append('default_%s' % defaultPass.next())

        highPass = iter(xrange(99))
        def highPrio():
            trace.append('high_%s' % highPass.next())

        lowPass = iter(xrange(99))
        def lowPrio():
            trace.append('low_%s' % lowPass.next())

        reactor.addProcess(defaultPrio)  # prio will be 0, "very high"
        reactor.addProcess(highPrio, prio=1)
        reactor.addProcess(lowPrio, prio=3)

        reactor.step()
        self.assertEquals([
                'default_0',
            ], trace)

        reactor.step()
        self.assertEquals(set([
                'default_0',
                'high_0', 'default_1',
            ]), set(trace))

        reactor.step()
        self.assertEquals(set([
                'default_0',
                'high_0', 'default_1',
                'high_1', 'default_2',
            ]), set(trace))

        reactor.step()
        self.assertEquals(set([
                'default_0',
                'high_0', 'default_1',
                'high_1', 'default_2',
                'high_2', 'low_0', 'default_3',
            ]), set(trace))

    def testProcessWithSuspend(self):
        reactor = Reactor()

        trace = []
        def p():
            trace.append(reactor.suspend())
            trace.append('suspending')
            yield
            trace.append('resuming')
            yield
        callback = p().next
        reactor.addProcess(callback)
        reactor.addProcess(lambda: reactor.removeProcess())
        reactor.step()
        self.assertEquals([callback], reactor._suspended.keys())
        self.assertEquals([callback, 'suspending'], trace)

        readers, _, _ = select([reactor._processReadPipe], [], [], 0.01)
        self.assertEquals([], readers)

        reactor.resumeProcess(handle=callback)
        readers, _, _ = select([reactor._processReadPipe], [], [], 0.01)
        self.assertEquals([reactor._processReadPipe], readers)

        reactor.step()
        self.assertEquals([], reactor._suspended.keys())
        self.assertEquals([callback, 'suspending', 'resuming'], trace)

    def testShutdownWithRemainingProcesses(self):
        reactor = Reactor()
        lambdaFunc = lambda: None
        reactor.addProcess(lambdaFunc)
        self.assertEquals([lambdaFunc], reactor._processes.keys())
        self.assertEquals('Reactor shutdown: terminating %s\n' % lambdaFunc, self.withSTDOUTRedirected(reactor.shutdown))
        self.assertEquals([], reactor._processes.keys())

        reactor = Reactor()
        lambdaFunc = lambda: reactor.suspend()
        reactor.addProcess(lambdaFunc)
        reactor.step()

        self.assertEquals([lambdaFunc], reactor._suspended.keys())
        self.assertEquals('Reactor shutdown: terminating %s\n' % lambdaFunc, self.withSTDOUTRedirected(reactor.shutdown))
        self.assertEquals([], reactor._suspended.keys())

    def testExceptionsInProcessNotSuppressed(self):
        reactor = Reactor()

        def p():
            raise RuntimeError('The Error')

        reactor.addProcess(p)
        self.assertEquals([p], reactor._processes.keys())
        try:
            reactor.step()
            self.fail('Should not come here.')
        except RuntimeError, e:
            self.assertEquals('The Error', str(e))
            self.assertEquals([], reactor._processes.keys())

    def testAddProcessFromThread(self):
        processCallback = []
        timerCallback = []
        reactor = Reactor()
        reactor.addTimer(1, self.fail)
        t = Thread(target=reactor.step)
        t.start()
        proc = lambda: processCallback.append(True)
        reactor.addProcess(proc)
        t.join()
        self.assertEquals([True], processCallback)

        reactor.removeProcess(proc)
        reactor.addTimer(0.1, lambda: timerCallback.append(True))
        reactor.step()
        self.assertEquals([True], processCallback)
        self.assertEquals([True], timerCallback)

    def withSTDOUTRedirected(self, function, expectedOutput=None):
        stream = StringIO()
        sys.stdout = stream
        try:
            function()
        finally:
            sys.stdout = sys.__stdout__
            value = stream.getvalue()
            if not expectedOutput is None:
                self.assertEquals(expectedOutput, value)
        return value

