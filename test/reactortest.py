#!/usr/bin/env python2.5
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2008 Seek You Too (CQ2) http://www.cq2.nl
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
#
from unittest import TestCase
from cq2utils.calltrace import CallTrace
from time import time, sleep
from signal import signal, SIGALRM, alarm, pause
from select import error as ioerror
import os, sys
from tempfile import mkstemp
from StringIO import StringIO
from weightless import Reactor

class ReactorTest(TestCase):

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
            while not self.time:
                reactor.step()
            self.assertTrue(self.alarm)
            self.assertTrue(targetTime - 0.01 < self.time, targetTime + 0.01)
        except ioerror:
            self.fail('must not fail on Interrupted system call')

    def testGetRidOfBadFileDescriptors(self):
        reactor = Reactor()
        self.timeout = False
        def timeout():
            self.timeout = True
        reactor.addReader(99, None) # broken
        reactor.addWriter(99, None) # broken
        reactor.addTimer(0.01, timeout)
        for i in range(10):
            if self.timeout:
                break
            reactor.step()
        self.assertTrue(self.timeout)

    def testDoNotDieButLogOnProgrammingErrors(self):
        reactor = Reactor()
        reactor.addReader('not a sok', None)
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
            pass
