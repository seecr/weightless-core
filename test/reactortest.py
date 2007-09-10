#!/usr/bin/env python2.5
## begin license ##
#
#    "Weightless" is a package with a wide range of valuable tools.
#    Copyright (C) 2005, 2006 Seek You Too B.V. (CQ2) http://www.cq2.nl
#
#    This file is part of "Weightless".
#
#    "Weightless" is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    "Weightless" is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with "Weightless"; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
#
from unittest import TestCase
from cq2utils.calltrace import CallTrace
from time import time
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
        self.assertTrue(0.045 < time() - start < 0.055)
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
            self.assertEquals('Timeout must be greater than 0. It was -1.', str(e))

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