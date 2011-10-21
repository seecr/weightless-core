# encoding: utf-8
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
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
from __future__ import with_statement
from contextlib import contextmanager
from socket import socket
from random import randint
from time import time
from StringIO import StringIO
import sys, string, os
from tempfile import mkdtemp, mkstemp
from shutil import rmtree

from unittest import TestCase
from threading import Thread
from weightless.io import Reactor

class WeightlessTestCase(TestCase):

    def setUp(self):
        self.tempdir = mkdtemp()
        fd, self.tempfile = mkstemp()
        os.close(fd)
        self.reactor = Reactor()
        self.mockreactor = Reactor(lambda r, w, o, t: (r, w, o))
        self.port = randint(2**15, 2**16)

    def tearDown(self):
        t0 = time()
        self.assertEquals({}, self.reactor._readers)
        self.assertEquals({}, self.reactor._writers)
        self.assertEquals({}, self.reactor._suspended)
        for t in self.reactor._timers:
            cb = t.callback
            code = cb.func_code
            print 'WARNING: dangling timer in reactor. Remaining timout: %s with callback to %s() in %s at line %s.' \
                % (t.time-t0, cb.func_name, code.co_filename, code.co_firstlineno)
        self.assertEquals([], self.reactor._timers)
        self.reactor.shutdown()
        rmtree(self.tempdir)
        os.remove(self.tempfile)

    def select(self, aString, index):
        while index < len(aString):
            char = aString[index]
            index = index + 1
            if not char in string.whitespace:
                return char, index
        return '', index

    def cursor(self, aString, index):
        return aString[:index - 1] + "---->" + aString[index - 1:]

    def assertEqualsWS(self, s1, s2):
        index1 = 0
        index2 = 0
        while True:
            char1, index1 = self.select(s1, index1)
            char2, index2 = self.select(s2, index2)
            if char1 != char2:
                self.fail('%s != %s' % (self.cursor(s1, index1), self.cursor(s2, index2)))
            if not char1 or not char2:
                break


    def send(self, host, port, message):
        sok = socket()
        sok.connect((host, port))
        sok.sendall(message)
        return sok

    def httpGet(self, host, port, path):
        return self.send(host, port, 'GET %(path)s HTTP/1.0\r\n\r\n' % locals())

    def httpPost(self, host='localhost', port=None, path='/', data='', contentType='text/plain'):
        return self.send(host, port or self.port,
            'POST %s HTTP/1.0\r\n' % path +
            'Content-Type: %s; charset=\"utf-8\"\r\n' % contentType +
            'Content-Length: %s\r\n' % len(data) +
            '\r\n' +
            data)

    @contextmanager
    def loopingReactor(self, timeOutInSec = 3):
        blockEnd = False
        timerHasFired = []
        def timeOut():
            timerHasFired.append(True)
        timer = self.reactor.addTimer(timeOutInSec, timeOut)
        def loop():
            while not(timerHasFired or blockEnd):
                t = self.reactor.addTimer(0.01, lambda: None)
                try:
                    self.reactor.step()
                finally:
                    try: self.reactor.removeTimer(t)
                    except ValueError: pass
        thread = Thread(None, loop)
        thread.start()
        try:
            yield
        finally:
            blockEnd = True
            assert not timerHasFired
            self.reactor.removeTimer(timer)
            thread.join()

    @contextmanager
    def stderr_replaced(self):
        oldstderr = sys.stderr
        mockStderr = StringIO()
        sys.stderr = mockStderr
        try:
            yield mockStderr
        finally:
            sys.stderr = oldstderr

    @contextmanager
    def stdout_replaced(self):
        oldstdout = sys.stdout
        mockStdout = StringIO()
        sys.stdout = mockStdout
        try:
            yield mockStdout
        finally:
            sys.stdout = oldstdout

class MatchAll(object):
    def __eq__(self, other):
        return True
    def __ne__(self, other):
        return False
    def __repr__(self):
        return '*MatchAll*'

MATCHALL = MatchAll()
