## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2015, 2018-2019 Seecr (Seek You Too B.V.) http://seecr.nl
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
from seecr.test.io import stderr_replaced, stdout_replaced
from testutils import readAndWritable, nrOfOpenFds, setTimeout, abortTimeout, BlockedCallTimedOut, installTimeoutSignalHandler
from wl_io.utils.testutils import dieAfter

import os, sys

from StringIO import StringIO
from errno import EPERM, EBADF, EINTR, EIO
from inspect import currentframe
from select import error as ioerror, select
from socket import socketpair, error, socket
from tempfile import mkstemp
from threading import Thread
from time import time, sleep

from weightless.core.utils import identify
from weightless.io import Reactor, reactor
from weightless.io.utils import asProcess, sleep as zleep

from weightless.io._reactor import EPOLLIN, EPOLL_TIMEOUT_GRANULARITY, _FDContext, _ProcessContext, _shutdownMessage


class ReactorTest(WeightlessTestCase):
    def setUp(self):
        WeightlessTestCase.setUp(self)
        self._revertTimeoutSignalHandler = installTimeoutSignalHandler()

    def tearDown(self):
        self._revertTimeoutSignalHandler()
        WeightlessTestCase.tearDown(self)

    def testAsContextManagerForTesting_onExitShutdownCalled(self):
        with Reactor() as reactor:
            loggedShutdowns = instrumentShutdown(reactor)

        self.assertEquals(1, len(loggedShutdowns))
        self.assertEquals(((), {}), loggedShutdowns[0])

    def testAsContextManagerForTesting_Stepping(self):
        log = []
        with Reactor() as reactor:
            p = lambda: log.append(True)
            loggedShutdowns = instrumentShutdown(reactor)
            reactor.addProcess(process=p)
            reactor.step()
            reactor.step()
            reactor.removeProcess(process=p)

        self.assertEquals(2, len(log))
        self.assertEquals(1, len(loggedShutdowns))

    def testAsContextManagerForTesting_LoopBreak(self):
        # Reactor context-manager & .loop is overkill; 1x shutdown is enough;
        # just don't want things to break because of this.
        with Reactor() as reactor:
            def raiser():
                reactor.removeProcess()
                raise Exception(42)
            loggedShutdowns = instrumentShutdown(reactor)
            reactor.addProcess(process=raiser)
            try:
                reactor.loop()
            except Exception, e:
                self.assertEquals(42, e.args[0])

        self.assertEquals(2, len(loggedShutdowns))

    def testAddSocketReading(self):
        with Reactor() as reactor:
            rw = readAndWritable()
            self.assertTrue(rw.fileno() not in reactor._fds)
            reactor.addReader(rw, lambda: None)
            self.assertTrue(rw.fileno() in reactor._fds)
            reactor.removeReader(rw)
            self.assertFalse(rw.fileno() in reactor._fds)

    def testAddSocketWriting(self):
        rw = readAndWritable()

        with Reactor() as reactor:
            self.assertTrue(rw.fileno() not in reactor._fds)
            reactor.addWriter(rw, None)
            self.assertTrue(rw.fileno() in reactor._fds)
            reactor.removeWriter(rw)
            self.assertFalse(rw.fileno() in reactor._fds)

    def testAddSocketRaisesException(self):
        class Sok: # raise exception when put into set
            def __hash__(self): raise Exception('aap')

        with Reactor() as reactor:
            try:
                reactor.addReader(Sok(), None)
                self.fail()
            except Exception, e:
                self.assertEquals('aap', str(e))

    def testReadable(self):
        with Reactor() as reactor:
            r, w = os.pipe()
            os.write(w, 'x')
            def readable():
                self.readable = True
            reactor.addReader(r, readable)
            reactor.step()
            self.assertTrue(self.readable)

            # cleanup
            reactor.removeReader(r)
            os.close(r); os.close(w)

    def testTimer(self):
        with Reactor() as reactor:
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
        with Reactor() as reactor:
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
        with Reactor() as reactor:
            try:
                reactor.addTimer(-1, None)
                self.fail('should raise exeption')
            except Exception, e:
                self.assertEquals('Timeout must be >= 0. It was -1.', str(e))

    def testDuplicateTimerDoesNotCauseZeroTimeout(self):
        itstime = []
        def itsTime():
            itstime.append(True)

        with Reactor() as reactor:
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

        with Reactor() as reactor:
            token1 = reactor.addTimer(0.05, itsTime)
            token2 = reactor.addTimer(0.051, itsTime)
            reactor.removeTimer(token1)
            self.assertEquals(1, len(reactor._timers))

    def testRemoveTimerById(self):
        def itsTime(): pass

        with Reactor() as reactor:
            token1 = reactor.addTimer(0.051, itsTime)
            token2 = reactor.addTimer(0.051, itsTime)
            token3 = reactor.addTimer(0.051, itsTime)
            token3.time = token2.time = token1.time  # whiteboxing, can happen in real code, not easy to reproduce in a test situation.
            self.assertEquals(token1.callback, token2.callback)
            self.assertEquals(token2.callback, token3.callback)
            reactor.removeTimer(token2)
            self.assertEquals([token1, token3], reactor._timers)

    def testRemoveTimerWithSameTimestamp(self):
        with Reactor() as reactor:
            token1 = reactor.addTimer(1, lambda: None)
            token2 = reactor.addTimer(1, lambda: None)
            token2.time = token1.time

            reactor.removeTimer(token2)
            self.assertEquals([id(token1)], [id(t) for t in reactor._timers])
            reactor.removeTimer(token1)
            self.assertEquals([], reactor._timers)

    def testRemoveEffectiveImmediately(self):
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
            rw.close()
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
            rw.close()
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
        with stderr_replaced():
            with Reactor() as reactor:
                def itsTime(): raise Exception('here is the exception')
                token1 = reactor.addTimer(0.001, itsTime)
                try:
                    reactor.step()
                except:
                    self.fail('must not raise exception')

    def testSelfModifyingLoopSkipsEverySecondTimerAndDeletesTheWrongOneBUG(self):
        done = []
        with Reactor() as reactor:
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

    def testWriteAfterReadMustHappenInTheNextStep(self):
        # Since readyness-event interested in changes for the fd - the fd must visit epoll_wait and be ready before being executed
        rwFd = readAndWritable()
        log = []
        with Reactor() as reactor:
            def writeCb():
                log.append('write')
            def readCb():
                log.append('read')
                reactor.removeReader(sok=rwFd)
                reactor.addWriter(sok=rwFd, source=writeCb)
            reactor.addReader(sok=rwFd, sink=readCb)

            self.assertEquals([], log)
            reactor.step()
            self.assertEquals(['read'], log)
            reactor.step()
            self.assertEquals(['read', 'write'], log)

            # cleanup
            reactor.removeWriter(sok=rwFd)
            rwFd.close()

    def testHandleReaderOrWriterWithCallbackGivingError(self):
        # Must be unregister / removed from epoll - otherwise epoll's polling loop becomes busy-waiting.
        log = []
        def raiser():
            log.append(True)
            raise ValueError('Really Bad!')

        def addWriter(reactor, sok, fn):
            reactor.addWriter(sok=sok, source=fn)

        def addReader(reactor, sok, fn):
            reactor.addReader(sok=sok, sink=fn)

        @dieAfter(seconds=5)
        def test(addFn):
            del log[:]
            rwFd = readAndWritable()
            try:
                r = reactor()
                addFn(r, sok=rwFd, fn=raiser)
                self.assertEquals(1, len(r._fds))
                # Executed once, and removed on error:
                for i in range(2):
                    yield zleep(0.05)
                    self.assertEquals(1, len(log))

                self.assertEquals(0, len(r._fds))
                self.assertEquals(0, len(r._badFdsLastCallback))
                self.assertEquals(0, len(r._suspended))
                self.assertEquals(1, len(r._processes))
                self.assertEquals(1, len(r._timers))

                # asProcesses' process(pipe) is expected
                self.assertEquals(set([r._processReadPipe]), fdsReadyFromReactorEpoll(r))
            finally:
                rwFd.close()

        with stderr_replaced() as err:
            asProcess(test(addFn=addWriter))
            asProcess(test(addFn=addReader))
            self.assertEquals([], [l for l in err.getvalue().lower().split('\n') if all([
                bool(l),
                l.find('traceback') == -1,
                l.find('file ') == -1,
                l.find('valueerror') == -1,
                l.find('callback()') == -1,
            ])], err.getvalue())

    def testAssertionErrorInReadCallback(self):
        rwFd = readAndWritable()
        with stderr_replaced():
            with Reactor() as reactor:
                def callback(): raise AssertionError('here is the assertion')
                reactor.addReader(rwFd, callback)
                try:
                    reactor.step()
                    self.fail('must raise exception')
                except AssertionError, e:
                    self.assertEquals('here is the assertion', str(e))

                # cleanup your administration on the way out
                self.assertEquals(0, fdsLenFromReactor(reactor))
                self.assertEquals(set(), fdsReadyFromReactorEpoll(reactor))

    def testAssertionErrorInWRITECallback(self):
        rwFd = readAndWritable()
        with stderr_replaced():
            with Reactor() as reactor:
                def callback(): raise AssertionError('here is the assertion')
                reactor.addWriter(rwFd, callback)
                try:
                    reactor.step()
                    self.fail('must raise exception')
                except AssertionError, e:
                    self.assertEquals('here is the assertion', str(e))

                # cleanup your administration on the way out
                self.assertEquals(0, fdsLenFromReactor(reactor))
                self.assertEquals(set(), fdsReadyFromReactorEpoll(reactor))

    def testWriteFollowsRead(self):
        with Reactor() as reactor:
            rw1 = readAndWritable()
            rw2 = readAndWritable()
            t = []
            def read():
                t.append('t1')
            def write():
                t.append('t2')
            reactor.addWriter(rw1, write)
            reactor.addReader(rw2, read)
            reactor.step()
            self.assertEquals(['t1', 't2'], t)

            # cleanup
            reactor.removeWriter(rw1)
            reactor.removeReader(rw2)
            rw1.close()
            rw2.close()

    def testReadDeletesWrite(self):
        with Reactor() as reactor:
            rw1 = readAndWritable()
            rw2 = readAndWritable()
            self.read = self.write = False
            def read():
                self.read = True
                reactor.removeWriter(rw1)
            def write():
                self.write = True
            reactor.addWriter(rw1, write)
            reactor.addReader(rw2, read)
            reactor.step()
            self.assertTrue(self.read)
            self.assertFalse(self.write)

            # cleanup
            reactor.removeReader(rw2)
            rw1.close(); rw2.close()

    def testReadFollowsTimer(self):
        with Reactor() as reactor:
            rwFd = readAndWritable()
            t = []
            def timer():
                t.append('t1')
            def read():
                t.append('t2')
            reactor.addTimer(0, timer)
            reactor.addReader(rwFd, read)
            reactor.step()
            self.assertEquals(['t1', 't2'], t)

            # cleanup
            reactor.removeReader(rwFd)
            rwFd.close()

    def testTimerDeletesRead(self):
        with Reactor() as reactor:
            rwFd = readAndWritable()
            self.read = self.timer = False
            def read():
                self.read = True
            def timer():
                self.timer = True
                reactor.removeReader(rwFd)
            reactor.addTimer(0, timer)
            reactor.addReader(rwFd, read)
            reactor.step()
            self.assertTrue(self.timer)
            self.assertFalse(self.read)

            # cleanup
            rwFd.close()

    def testInterruptedEpollWaitDoesNotDisturbTimer(self):
        with Reactor() as reactor:
            self.time = False
            def timeout():
                self.time = time()
            def signalTimeout():
                self.alarm = True
            targetTime = time() + 0.04
            reactor.addTimer(0.04, timeout)
            setTimeout(0.01, callback=signalTimeout)
            try:
                with self.stderr_replaced() as s:
                    while not self.time:
                        reactor.step()
                    self.assertTrue("[Errno 4] Interrupted system call" in s.getvalue(), s.getvalue())
                self.assertTrue(self.alarm)
                self.assertTrue(targetTime - 0.01 < self.time, targetTime + 0.01)
            except ioerror:
                self.fail('must not fail on Interrupted system call')

    def testGetRidOfBadFileDescriptors(self):
        with Reactor() as reactor:
            FD_HIGHER_THAN_ANY_EXISTING = 250  # TRICKY: select internals leak; use value representable in 1 byte!
            self.assertTrue(FD_HIGHER_THAN_ANY_EXISTING > nrOfOpenFds() + 5, nrOfOpenFds())  # Some margin; can give false positives (nr_of_fds != (highest_fd_number - 1))
            class BadSocket(object):
                def fileno(self): return FD_HIGHER_THAN_ANY_EXISTING
                def close(self): raise Exception('hell breaks loose')
            self.timeout = False
            def timeout():
                self.timeout = True
            with self.stderr_replaced() as s:
                reactor.addReader(FD_HIGHER_THAN_ANY_EXISTING + 1, lambda: None) # broken
                reactor.addWriter(FD_HIGHER_THAN_ANY_EXISTING + 1, lambda: None) # broken
                reactor.addReader(BadSocket(), lambda: None) # even more broken
                self.assertTrue("Bad file descriptor" in s.getvalue(), repr(s.getvalue()))
            reactor.addTimer(0.01, timeout)
            for i in range(10):
                if self.timeout:
                    break
                reactor.step()
            self.assertEquals({}, reactor._fds)
            self.assertEquals([], reactor._timers)
            self.assertTrue(self.timeout)

    def testGetRidOfClosedSocket(self):
        with Reactor() as reactor:
            sok = socket()
            sok.close()
            callbacks = []
            def callback():
                callbacks.append(True)
            with self.stderr_replaced() as s:
                reactor.addReader(sok, callback)
                reactor.addWriter(sok, callback)
                self.assertTrue("Bad file descriptor" in s.getvalue(), s.getvalue())
            self.assertEquals({}, reactor._fds)
            self.assertEquals([], callbacks)
            reactor.step()
            self.assertEquals([True, True], callbacks)

    def testClosedOrOtherwiseBadFDNotAddedButCallbackCalledOnce(self):
        rw = readAndWritable()
        rw.close()
        log = []
        with Reactor() as reactor:
            with stderr_replaced() as err:
                reactor.addReader(sok=rw, sink=lambda: log.append(True))
                self.assertTrue('Bad file descriptor' in err.getvalue(), err.getvalue())
            self.assertEquals(0, len(log))
            self.assertEquals(1, len(reactor._badFdsLastCallback))

            reactor.step()

            self.assertEquals(1, len(log))
            self.assertEquals(0, len(reactor._badFdsLastCallback))

    def testRemoveReaderOrWriterWithEBADFDoesNotLeak(self):
        rw1 = readAndWritable()  # add; step; EBADF; remove
        rw2 = readAndWritable()  # add; EBADF; remove
        rw3 = readAndWritable()  # added; EBADF; step; remove
        log = []
        with Reactor() as reactor:
            reactor.addReader(sok=rw1, sink=lambda: log.append("rw1"))

            reactor.step()
            self.assertEquals(1, len(log))

            reactor.addWriter(sok=rw2, source=lambda: log.append("rw2"))
            reactor.addWriter(sok=rw3, source=lambda: log.append("rw3"))

            # EBADF Them!
            rw1.close(); rw2.close(); rw3.close()

            with stderr_replaced() as err:
                reactor.removeReader(sok=rw1)
                reactor.removeWriter(sok=rw2)
                self.assertEquals(2, err.getvalue().count('Errno 9'), err.getvalue())

            reactor.addTimer(seconds=0.001, callback=lambda: log.append("t1"))
            reactor.step()

            with stderr_replaced() as err:
                reactor.removeWriter(sok=rw3)
                self.assertEquals(1, err.getvalue().count('Errno 9'), err.getvalue())

            self.assertEquals(["rw1", "t1"], log)
            self.assertEquals(0, len(reactor._fds))

    def testAddNotAFileOrFdNotAddedButCallbackCalledOnce(self):
        notAFile = "I'm not a file."
        log = []
        with Reactor() as reactor:
            with stderr_replaced() as err:
                reactor.addReader(sok=notAFile, sink=lambda: log.append(True))
                self.assertTrue('argument must be an int, or have a fileno() method' in err.getvalue(), err.getvalue())
            self.assertEquals(0, len(log))
            self.assertEquals(1, len(reactor._badFdsLastCallback))

            reactor.step()

            self.assertEquals(1, len(log))
            self.assertEquals(0, len(reactor._badFdsLastCallback))

    def testDoNotDieButLogOnProgrammingErrors(self):
        called = []
        cb = lambda: called.append(True)
        with Reactor() as reactor:
            with stderr_replaced() as err:
                try:
                    reactor.addReader('not a sok', cb)
                except TypeError:
                    self.fail('must not fail')
                self.assertTrue('TypeError: argument must be an int' in err.getvalue())

            self.assertEquals([], called)
            self.assertEquals([cb], [c.callback for c in reactor._badFdsLastCallback])
            reactor.step()
            self.assertEquals([True], called)
            self.assertEquals([], [c.callback for c in reactor._badFdsLastCallback])

    def testDoNotMaskOtherErrors(self):
        # TS: TODO: rewrite!
        reactor = Reactor()
        reactor._epoll.close()  # Simples wat to get an "unexpected" error from epoll.poll()
        try:
            reactor.step()
            self.fail()
        except Exception, e:
            self.assertEquals('I/O operation on closed epoll fd', str(e))

    def testTimerDoesNotMaskAssertionErrors(self):
        with Reactor() as reactor:
            reactor.addTimer(0, lambda: self.fail("Assertion Error"))
            try:
                reactor.step()
                raise Exception('step() must raise AssertionError')
            except AssertionError:
                self.assertEquals([], reactor._timers)

    def testTimerDoesNotMaskKeyboardInterrupt(self):
        with Reactor() as reactor:
            def raiser():
                raise KeyboardInterrupt('Ctrl-C')
            reactor.addTimer(0, raiser)
            try:
                reactor.step()
                self.fail('step() must raise KeyboardInterrupt')
            except KeyboardInterrupt:
                self.assertEquals([], reactor._timers)

    def testTimerDoesNotMaskSystemExit(self):
        with Reactor() as reactor:
            def raiser():
                raise SystemExit('shutdown...')
            reactor.addTimer(0, raiser)
            try:
                reactor.step()
                self.fail('step() must raise SystemExit')
            except SystemExit:
                self.assertEquals([], reactor._timers)

    def testReaderOrWriterDoesNotMaskKeyboardInterrupt(self):
        rw = readAndWritable()
        try:
            with Reactor() as reactor:
                def raiser():
                    raise KeyboardInterrupt('Ctrl-C')
                reactor.addReader(sok=rw, sink=raiser)
                self.assertEquals([raiser], [c.callback for c in reactor._fds.values()])
                try:
                    reactor.step()
                    self.fail('step() must raise KeyboardInterrupt')
                except KeyboardInterrupt:
                    self.assertEquals([], [c.callback for c in reactor._fds.values()])
        finally:
            rw.close()

        rw = readAndWritable()
        try:
            with Reactor() as reactor:
                reactor.addWriter(sok=rw, source=raiser)
                try:
                    reactor.step()
                    self.fail('step() must raise KeyboardInterrupt')
                except KeyboardInterrupt:
                    self.assertEquals([], [c.callback for c in reactor._fds.values()])
        finally:
            rw.close()

    def testReaderOrWriterDoesNotMaskSystemExit(self):
        rw = readAndWritable()
        try:
            with Reactor() as reactor:
                def raiser():
                    raise SystemExit('shutdown...')
                reactor.addReader(sok=rw, sink=raiser)
                self.assertEquals([raiser], [c.callback for c in reactor._fds.values()])
                try:
                    reactor.step()
                    self.fail('step() must raise SystemExit')
                except SystemExit:
                    self.assertEquals([], [c.callback for c in reactor._fds.values()])
        finally:
            rw.close()

        rw = readAndWritable()
        try:
            with Reactor() as reactor:
                reactor.addWriter(sok=rw, source=raiser)
                try:
                    reactor.step()
                    self.fail('step() must raise SystemExit')
                except SystemExit:
                    self.assertEquals([], [c.callback for c in reactor._fds.values()])
        finally:
            rw.close()

    def testGlobalReactor(self):
        with Reactor() as thereactor:
            def handler():
                self.assertEquals(thereactor, reactor())
            thereactor.addTimer(0, handler)
            thereactor.step()

    def testReadPriorities(self):
        with Reactor() as reactor:
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

            # cleanup
            reactor.removeReader(remote0)
            reactor.removeReader(remote1)
            local0.close(); remote0.close()
            local1.close(); remote1.close()

    def testMinandMaxPrio(self):
        with Reactor() as reactor:
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
        with Reactor() as reactor:
            rw1 = readAndWritable()
            reactor.addReader(rw1, '')
            self.assertEquals(Reactor.DEFAULTPRIO, reactor._fds[rw1.fileno()].prio)
            rw2 = readAndWritable()
            reactor.addWriter(rw2, '')
            self.assertEquals(Reactor.DEFAULTPRIO, reactor._fds[rw2.fileno()].prio)

            # cleanup
            reactor.removeReader(rw1)
            reactor.removeWriter(rw2)

    def testWritePrio(self):
        with Reactor() as reactor:
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

            # cleanup
            reactor.removeWriter(remote0)
            reactor.removeWriter(remote1)
            local0.close(); remote0.close()
            local1.close(); remote1.close()

    def testGetOpenConnections(self):
        rw1 = readAndWritable()
        rw2 = readAndWritable()
        with Reactor() as reactor:
            self.assertEquals(0, reactor.getOpenConnections())
            reactor.addReader(rw1, '')
            self.assertEquals(1, reactor.getOpenConnections())
            reactor.addWriter(rw2, '')
            self.assertEquals(2, reactor.getOpenConnections())

            reactor.removeReader(rw1)
            self.assertEquals(1, reactor.getOpenConnections())
            reactor.removeWriter(rw2)
            self.assertEquals(0, reactor.getOpenConnections())

    def testAddProcessGenerator(self):
        with Reactor() as reactor:
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

            noop = lambda: None
            reactor.addProcess(process=noop)
            reactor.step()
            self.assertEquals([1, 2], trace)

            # cleanup
            reactor.removeProcess(process=noop)

    def testAddProcessFunction(self):
        with Reactor() as reactor:
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

            noop = lambda: None
            reactor.addProcess(noop)
            reactor.step()
            self.assertEquals([2, 4, 'removedProcess'], trace)

            # cleanup
            reactor.removeProcess(noop)

    def testAddProcessSanityCheck(self):
        with Reactor() as reactor:
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

            # cleanup
            reactor.resumeProcess(lambdaFunc)
            reactor.removeProcess(lambdaFunc)

    def testProcessAddsNotWhenAlreadyInThere(self):
        with Reactor() as reactor:
            aProcess = lambda: None
            reactor.addProcess(aProcess)
            try:
                reactor.addProcess(aProcess)
                self.fail('Should not come here.')
            except ValueError, e:
                self.assertEquals('Process is already in processes', str(e))

            # cleanup
            reactor.removeProcess(aProcess)

    def testProcessPriority(self):
        with Reactor() as reactor:
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

            # cleanup
            reactor.removeProcess(defaultPrio)
            reactor.removeProcess(highPrio)
            reactor.removeProcess(lowPrio)

    def testProcessWithSuspend(self):
        with Reactor() as reactor:
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

            # cleanup
            reactor.removeProcess(callback)

    def testShutdownWithRemainingProcesses(self):
        reactor = Reactor()
        lambdaFunc = lambda: None
        reactor.addProcess(lambdaFunc)
        self.assertEquals([lambdaFunc], reactor._processes.keys())
        with stdout_replaced() as out:
            reactor.shutdown()
            self.assertEquals(1, out.getvalue().count('Reactor shutdown: terminating - active: %s (process) with callback: %s at: ' % (lambdaFunc, lambdaFunc)), out.getvalue())
        self.assertEquals([], reactor._processes.keys())

        reactor = Reactor()
        lambdaFunc = lambda: reactor.suspend()
        reactor.addProcess(lambdaFunc)
        reactor.step()

        self.assertEquals([lambdaFunc], reactor._suspended.keys())
        with stdout_replaced() as out:
            reactor.shutdown()
            self.assertEquals(1, out.getvalue().count('Reactor shutdown: terminating - suspended: %s (process)' % lambdaFunc), out.getvalue())
        self.assertEquals([], reactor._suspended.keys())

    def testExceptionsInProcessNotSuppressed(self):
        with Reactor() as reactor:
            def p():
                raise RuntimeError('The Error')

            reactor.addProcess(p)
            self.assertEquals([p], reactor._processes.keys())
            self.assertEquals(0, fdsLenFromReactor(reactor))
            self.assertEquals(set([reactor._processReadPipe]), fdsReadyFromReactorEpoll(reactor))
            try:
                reactor.step()
                self.fail('Should not come here.')
            except RuntimeError, e:
                self.assertEquals('The Error', str(e))

            # cleanup your administration on the way out
            self.assertEquals([], reactor._processes.keys())
            self.assertEquals(0, fdsLenFromReactor(reactor))
            self.assertEquals(set(), fdsReadyFromReactorEpoll(reactor))

    def testSuspendCalledFromTimerNotAllowed(self):
        def callback():
            try:
                reactor.suspend()
                self.fail()
            except RuntimeError, e:
                self.assertTrue(str(e).startswith('suspend called from a timer'), str(e))
        with Reactor() as reactor:
            reactor.addTimer(seconds=0, callback=callback)
            reactor.step()

    def testSuspendCalledFromLastCallCallbackNotAllowed(self):
        def callback():
            try:
                reactor.suspend()
                self.fail()
            except RuntimeError, e:
                self.assertTrue(str(e).startswith('suspend called from a timer'), str(e))
        rw = readAndWritable()
        with Reactor() as reactor:
            rw.close()
            with stderr_replaced() as err:
                reactor.addWriter(sok=rw, source=callback)
                self.assertTrue('Bad file descriptor' in err.getvalue(), err.getvalue())
            reactor.step()

    def testSuspendCalledWhenCurrentcontextRemovedNotAllowed(self):
        # In 'old select-based Reactor; silently suspended something already removed.
        def process():
            _reactor = reactor()
            _reactor.removeProcess()
            try:
                _reactor.suspend()
                self.fail()
            except RuntimeError, e:
                self.assertEquals('Current context not found!', str(e))
        with Reactor() as thereactor:
            thereactor.addProcess(process=process)
            thereactor.step()

    def testUnexpectedFdInEpollFdEventsLoggedAndIgnored(self):
        # TS: Should *not* happen anymore - report to your commanding officer if it does!
        with Reactor() as reactor:
            rwFD = readAndWritable()
            rwFD_unexpected = readAndWritable()
            reactor.addReader(sok=rwFD, sink=lambda: None)

            # whitebox adding - since this should not be possible ...
            reactor._epoll.register(fd=rwFD_unexpected, eventmask=EPOLLIN)
            with stderr_replaced() as err:
                reactor.step()
                self.assertEquals('[Reactor]: epoll event fd %d does not exist in fds list.\n' % rwFD_unexpected.fileno(), err.getvalue(), err.getvalue())

            # cleanup
            reactor.removeReader(sok=rwFD)
            reactor.cleanup(rwFD_unexpected)


    def testRemoveFDAlsoEpollUnregisters(self):
        cb = lambda: None
        with Reactor() as reactor:
            # removeReader
            rwFD = readAndWritable()
            reactor.addReader(sok=rwFD, sink=cb)
            self.assertEquals(1, fdsLenFromReactor(reactor))
            self.assertEquals(set([rwFD.fileno()]), fdsReadyFromReactorEpoll(reactor))

            reactor.removeReader(rwFD)
            self.assertEquals(0, fdsLenFromReactor(reactor))
            self.assertEquals(set(), fdsReadyFromReactorEpoll(reactor))

            # removeReader (or any other thing calling _removeFD) -  with bad-fd
            rwFD = readAndWritable()
            reactor.addReader(sok=rwFD, sink=cb)
            rwFD.close()
            self.assertRaises(IOError, lambda: rwFD.fileno())

            with stderr_replaced() as err:
                reactor.removeReader(rwFD)
                self.assertTrue('error: [Errno 9]' in err.getvalue(), err.getvalue())
            self.assertEquals(0, fdsLenFromReactor(reactor))
            self.assertEquals(set(), fdsReadyFromReactorEpoll(reactor))

            # removeWriter
            rwFD = readAndWritable()
            reactor.addWriter(sok=rwFD, source=cb)
            self.assertEquals(1, fdsLenFromReactor(reactor))
            self.assertEquals(set([rwFD.fileno()]), fdsReadyFromReactorEpoll(reactor))

            reactor.removeWriter(rwFD)
            self.assertEquals(0, fdsLenFromReactor(reactor))
            self.assertEquals(set(), fdsReadyFromReactorEpoll(reactor))

            # suspend
            rwFD = readAndWritable()
            def suspendCb():
                reactor.suspend()
            reactor.addWriter(sok=rwFD, source=suspendCb)
            self.assertEquals(1, fdsLenFromReactor(reactor))
            self.assertEquals(set([rwFD.fileno()]), fdsReadyFromReactorEpoll(reactor))

            reactor.step()      # suspends
            self.assertEquals(0, fdsLenFromReactor(reactor))
            self.assertEquals(set(), fdsReadyFromReactorEpoll(reactor))
            self.assertEquals(1, len(reactor._suspended))

            # cleanup
            reactor.cleanup(rwFD)

    def testCleanupAlsoEpollUnregistersWhenPresent(self):
        cb = lambda: None
        with Reactor() as reactor:
            # normal
            rwFD = readAndWritable()
            reactor.addReader(sok=rwFD, sink=cb)
            self.assertEquals(1, fdsLenFromReactor(reactor))
            self.assertEquals(set([rwFD.fileno()]), fdsReadyFromReactorEpoll(reactor))

            reactor.cleanup(rwFD)
            self.assertEquals(0, fdsLenFromReactor(reactor))
            self.assertEquals(set(), fdsReadyFromReactorEpoll(reactor))

            # as a file-obj with a bad-file-descriptor
            rwFD = readAndWritable()
            reactor.addReader(sok=rwFD, sink=cb)
            self.assertEquals(1, fdsLenFromReactor(reactor))
            self.assertEquals(set([rwFD.fileno()]), fdsReadyFromReactorEpoll(reactor))

            rwFD.close()
            self.assertRaises(IOError, lambda: rwFD.fileno())
            with stderr_replaced() as err:
                reactor.cleanup(rwFD)
                self.assertTrue("[Errno 9] Bad file descriptor" in err.getvalue())
            self.assertEquals(0, fdsLenFromReactor(reactor))
            self.assertEquals(set(), fdsReadyFromReactorEpoll(reactor))


    def testCleanupOfReaderOrWriterFd(self):
        rw1 = readAndWritable()
        rw2 = readAndWritable()
        rw3 = readAndWritable()
        rw4 = readAndWritable()
        with Reactor() as reactor:
            reactor.addReader(sok=rw1, sink=lambda: reactor.suspend())
            reactor.addReader(sok=rw2, sink=lambda: reactor.suspend())
            reactor.step()

            rw2fileno = rw2.fileno()
            rw2.close()
            reactor.addReader(sok=rw3, sink=lambda: None)
            reactor.addReader(sok=rw4, sink=lambda: None)
            rw4.close()

            self.assertEquals(2, len(reactor._suspended))
            self.assertEquals(2, len(reactor._fds))

            reactor.cleanup(rw1)
            self.assertEquals(1, len(reactor._suspended))
            self.assertEquals([rw2fileno], reactor._suspended.keys())

            with stderr_replaced() as err:
                reactor.cleanup(rw2)
                self.assertTrue('Bad file descriptor' in err.getvalue(), err.getvalue())

            self.assertEquals(2, len(reactor._fds))
            self.assertEquals(0, len(reactor._suspended))

            with stderr_replaced() as err:
                reactor.cleanup(rw4)
                self.assertTrue('Bad file descriptor' in err.getvalue(), err.getvalue())
            self.assertEquals(1, len(reactor._fds))
            self.assertEquals([rw3.fileno()], reactor._fds.keys())
            reactor.cleanup(rw3)

            self.assertEquals(0, len(reactor._fds))
            self.assertEquals(0, len(reactor._suspended))

            # cleanup is like remove; no _badFdsLastCallback's
            self.assertEquals(0, len(reactor._badFdsLastCallback))

    def testAddProcessFromThread(self):
        with Reactor() as reactor:
            processCallback = []
            timerCallback = []
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

    def testTimerWithSecondsSmallerThanGranularityNotExecutedImmediately(self):
        noop = lambda: None
        with Reactor() as reactor:
            seconds = 0.00099
            self.assertTrue(seconds < EPOLL_TIMEOUT_GRANULARITY)
            steps = 0
            called = []
            reactor.addProcess(process=noop)
            reactor.addTimer(seconds=0.00099, callback=lambda: called.append(True))
            while not called:
                steps += 1
                reactor.step()

            self.assertTrue(steps > 1)

            # cleanup
            reactor.removeProcess(process=noop)

    def testTimerWakesUpReactorOnce(self):
        # Not "too soon"; and then have 1..n steps in which there is nothing to do (busy-wait).
        noop = lambda: None
        with Reactor() as reactor:
            seconds = 0.002
            steps = 0
            called = []
            reactor.addTimer(seconds=seconds, callback=lambda: called.append(True))
            while not called:
                steps += 1
                reactor.step()

            self.assertEquals(1, steps)

    def testShutdownClosesRemainingFilesAndClosableProcesses(self):
        log = []
        class MySocket(socket):
            def close(self):
                log.append(True)
                return socket.close(self)

        class P(object):
            def __call__(self):
                pass
            def close(self):
                log.append(True)

        class T(object):
            def __call__(self):
                raise AssertionError('Should not happen')
            def close(self):
                raise AssertionError('Should not happen')

        def notCalled():
            raise AssertionError('Should not happen')

        noop = lambda: None
        rw1 = MySocket()
        rw2 = MySocket()
        rwS = MySocket()
        BAD_FD = 1022  # Higher than any fd

        with Reactor() as reactor:
            reactor.addReader(sok=rwS, sink=lambda: reactor.suspend())
            reactor.step()  # suspend
            self.assertEquals(1, len(reactor._suspended))

            reactor.addTimer(seconds=0.01, callback=T())
            reactor.addReader(sok=rw1, sink=noop)
            with stderr_replaced() as err:
                reactor.addReader(sok=BAD_FD, sink=notCalled)
                self.assertTrue('Bad file descriptor' in err.getvalue(), err.getvalue())
                self.assertEquals(1, len(reactor._badFdsLastCallback))
            reactor.addWriter(sok=rw2, source=noop)
            reactor.addProcess(process=P())

            with stdout_replaced() as out:
                reactor.shutdown()
                self.assertEquals(4, out.getvalue().count('Reactor shutdown: closing'), out.getvalue())
                self.assertEquals(3, out.getvalue().count('(fd) with fd:'))
                self.assertEquals(2, out.getvalue().count(': noop = lambda: None'))
                self.assertEquals(1, out.getvalue().count('(process) with callback:'))
                self.assertEquals(1, out.getvalue().count(': def __call__(self):'))

            self.assertEquals(0, len(reactor._badFdsLastCallback))
            self.assertEquals(0, len(reactor._fds))
            self.assertEquals(0, len(reactor._processes))
            self.assertEquals(0, len(reactor._suspended))
            self.assertEquals(4, len(log))

    def testShutdownKeepsClosingOnFdLikeCloseErrors(self):
        log = []
        class MySocket1(socket):
            def close(self):
                log.append(True)
                socket.close(self)
                raise IOError(EBADF, 'Meh.')
        class MySocket2(socket):
            def close(self):
                log.append(True)
                socket.close(self)
                raise OSError(EINTR, 'Meh.')
        class MySocket3(socket):
            def close(self):
                log.append(True)
                socket.close(self)
                raise OSError(EIO, 'Meh.')

        noop = lambda: None
        rw1 = MySocket1()
        rw2 = MySocket2()
        rw3 = MySocket3()

        with Reactor() as reactor:
            reactor.addReader(sok=rw1, sink=noop)
            reactor.addReader(sok=rw2, sink=noop)
            reactor.addReader(sok=rw3, sink=noop)

            with stdout_replaced() as out:
                with stderr_replaced() as err:
                    reactor.shutdown()
                    self.assertEquals(3, err.getvalue().count('[Errno'), err.getvalue())
                self.assertEquals(3, out.getvalue().count('Reactor shutdown: closing'), out.getvalue())

            self.assertEquals(0, len(reactor._fds))
            self.assertEquals(3, len(log))

    def testShutdownClosesInternalFds(self):
        nfds = nrOfOpenFds()
        with Reactor() as reactor:
            pass
        self.assertEquals(nfds, nrOfOpenFds())

        nfds = nrOfOpenFds()
        with Reactor() as reactor:
            # 3 extra; because:
            #   - epoll(_create) fd
            #   - (process) pipe read end
            #   - (process) pipe write end
            self.assertEquals(nfds + 3, nrOfOpenFds())
            reactor.shutdown()
            self.assertEquals(nfds, nrOfOpenFds())
        self.assertEquals(nfds, nrOfOpenFds())  # 2nd shutdown; no change.

    def testAddDifferentFileObjWithSameFD(self):
        # Typically won't happen normally - but iff it ever happens, give a readable error.
        class MockRW(object):
            def __init__(self, rw):
                self._rw = rw
            def __getattr__(self, attr):
                return getattr(self._rw, attr)

        noop = lambda: None
        rw = readAndWritable()
        rwFile1 = MockRW(rw)
        rwFile2 = MockRW(rw)
        try:
            with Reactor() as reactor:
                reactor.addReader(sok=rwFile1, sink=noop)
                try:
                    reactor.addReader(sok=rwFile2, sink=noop)
                    self.fail()
                except ValueError, e:
                    self.assertEquals('fd already registered', str(e))

                # cleanup
                reactor.removeReader(sok=rwFile1)
        finally:
            rw.close()

    def testAddFileObjWhichIsEBADFAndSuspended(self):
        noop = lambda: None
        rw = readAndWritable()
        handle = []
        lastcall = []
        def sink():
            handle.append(reactor.suspend())
            yield
            lastcall.append(True)
            yield  # wait for GC
            raise AssertionError('Should not happen')
        try:
            with Reactor() as reactor:
                reactor.addReader(sok=rw, sink=sink().next)
                reactor.step()
                self.assertEquals(0, len(reactor._fds))
                self.assertEquals(1, len(reactor._suspended))

                # Going EBADF
                rw.close()

                with stderr_replaced() as err:
                    try:
                        reactor.addReader(sok=rw, sink=noop)
                        self.fail()
                    except ValueError, e:
                        self.assertEquals('Socket is suspended', str(e))
                    self.assertTrue('Bad file descriptor' in err.getvalue(), err.getvalue())
                    self.assertEquals(1, len(handle))
                    self.assertEquals(0, len(lastcall))
                    self.assertEquals(0, len(reactor._fds))
                    self.assertEquals(1, len(reactor._suspended))
                    self.assertEquals(0, len(reactor._badFdsLastCallback))

                with stderr_replaced() as err:
                    reactor.resumeReader(handle=handle[0])
                    self.assertTrue('Bad file descriptor' in err.getvalue(), err.getvalue())

                self.assertEquals(0, len(reactor._suspended))
                self.assertEquals(1, len(reactor._badFdsLastCallback))
                self.assertEquals(0, len(lastcall))

                reactor.step()

                self.assertEquals(0, len(reactor._badFdsLastCallback))
                self.assertEquals(1, len(lastcall))
        finally:
            rw.close()

    def testAddFileNotPossible(self):
        # or meaningful; non-blocking file interface does not exist on Linux (use Threads) and a file-fd cannot be registered in epoll.
        fd, path = mkstemp()
        try:
            with Reactor() as reactor:
                try:
                    with stderr_replaced() as err:
                        reactor.addReader(sok=fd, sink=lambda: None)
                        self.assertTrue('Operation not permitted' in err.getvalue(), err.getvalue())
                    self.fail()
                except IOError, (errno, description):
                    self.assertEquals(EPERM, errno)
                    self.assertEquals('Operation not permitted', description)
        finally:
            os.close(fd)
            os.remove(path)

    def testAddTimeoutLargerThanMaxInt(self):
        # maxIntEPoll = 2**31 -1
        # This test asserts that huge timers will not crash the epoll.poll function
        p = lambda: None
        with Reactor() as reactor:
            reactor.addTimer(2**50, lambda:None)
            reactor.addProcess(p)
            reactor.step()
            reactor.removeProcess(p)

    def testShutdownMessageMessage(self):
        # _FDContext - with fd-number
        fd = 7
        line = __NEXTLINE__()
        cb = lambda: 'cb'
        result = _shutdownMessage(message='message', thing=fd, context=_FDContext(callback=cb, fileOrFd=fd, intent='ignored-here', prio=9))
        expected = "Reactor shutdown: message: %(fd)s (fd) with fd: %(fd)s with callback: %(cb)s at: %(TESTFILE)s: %(line)s: cb = lambda: 'cb'" % dict(locals(), **globals())
        self.assertEquals(expected, result)

        # _FDContext - with fd-obj and callable-obj
        fd = 7
        line = __NEXTLINE__(offset=1)
        class O(object):
            def __call__(self):
                pass
        class F(object):
            def fileno(self):
                return fd
        thing = F()
        cb = O()
        result = _shutdownMessage(message='M !', thing=thing, context=_FDContext(callback=cb, fileOrFd=thing, intent='ignored-here', prio=9))
        expected = "Reactor shutdown: M !: %(thing)s (fd) with fd: %(fd)s with callback: %(cb)s at: %(TESTFILE)s: %(line)s: def __call__(self):" % dict(locals(), **globals())
        self.assertEquals(expected, result)

        # _ProcessContext - with callable
        line = __NEXTLINE__()
        cb = lambda: None
        result = _shutdownMessage(message='m', thing=cb, context=_ProcessContext(callback=cb, prio=1))
        expected = "Reactor shutdown: m: %(cb)s (process) with callback: %(cb)s at: %(TESTFILE)s: %(line)s: cb = lambda: None" % dict(locals(), **globals())
        self.assertEquals(expected, result)

        # _ProcessContext - with <generator>.next
        line = __NEXTLINE__()
        def g():
            return
            yield
        cb = g().next
        result = _shutdownMessage(message='m', thing=cb, context=_ProcessContext(callback=cb, prio=1))
        expected = "Reactor shutdown: m: %(cb)s (process) with callback: %(cb)s at: %(TESTFILE)s: %(line)s: def g():" % dict(locals(), **globals())
        self.assertEquals(expected, result)

    def testShutdownMessageUnsourceable(self):
        # Verify odd / not getsourcelines- or getsourcefile-able callback gives no errors (just less info).
        # _ProcessContext - with uncallable
        cb = object()
        result = _shutdownMessage(message='m', thing=cb, context=_ProcessContext(callback=cb, prio=1))
        expected = "Reactor shutdown: m: %(cb)s (process) with callback: %(cb)s" % dict(locals(), **globals())
        self.assertEquals(expected, result)

        # _ProcessContext - with uncallable
        cb = "not-a-function"
        result = _shutdownMessage(message='m', thing=cb, context=_ProcessContext(callback=cb, prio=1))
        expected = "Reactor shutdown: m: %(cb)s (process) with callback: %(cb)s" % dict(locals(), **globals())
        self.assertEquals(expected, result)

        # _ProcessContext - with built-in
        cb = str  # built-in - *source* don't like that.
        result = _shutdownMessage(message='m', thing=cb, context=_ProcessContext(callback=cb, prio=1))
        expected = "Reactor shutdown: m: %(cb)s (process) with callback: %(cb)s" % dict(locals(), **globals())
        self.assertEquals(expected, result)

        # _FDContext - fd-object /w issues (IOError / OSError or socket_error) and an unlucky callback.
        class F(object):
            def fileno(self):
                raise IOError("Whoops!")  # errno & message stuff usually - not important here.
        f = F()
        cb = str  # built-in
        result = _shutdownMessage(message='m', thing=f, context=_FDContext(callback=cb, fileOrFd=f, intent='ignored-here', prio=9))
        expected = "Reactor shutdown: m: %(f)s (fd) with callback: %(cb)s" % dict(locals(), **globals())
        self.assertEquals(expected, result)


def instrumentShutdown(reactor):
    loggedShutdowns = []
    shutdown = reactor.shutdown
    def mockedShutdown(*args, **kwargs):
        loggedShutdowns.append((args, kwargs))
        return shutdown(*args, **kwargs)
    reactor.shutdown = mockedShutdown
    return loggedShutdowns

def fdsReadyFromReactorEpoll(reactor):
    return set([fd for (fd, _) in reactor._epoll.poll(timeout=0)])

def fdsLenFromReactor(reactor):
    return len(reactor._fds)

def __NEXTLINE__(offset=0):
    return currentframe().f_back.f_lineno + offset + 1

TESTFILE = __file__.replace(".pyc", ".py")
