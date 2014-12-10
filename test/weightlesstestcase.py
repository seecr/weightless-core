# encoding: utf-8
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2014 Seecr (Seek You Too B.V.) http://seecr.nl
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

from contextlib import contextmanager
from operator import xor
from random import randint
from socket import AF_INET, SOCK_STREAM, socket
from time import time

from os.path import join, dirname, abspath
from io import StringIO
import sys, string, os
from tempfile import mkdtemp, mkstemp
from shutil import rmtree

from unittest import TestCase
from threading import Thread, Event
from weightless.io import Reactor

from http.server import BaseHTTPRequestHandler
from socketserver import TCPServer, ThreadingMixIn, BaseServer
from ssl import wrap_socket
from urllib.request import urlopen
from select import select
from urllib.parse import urlunparse, urlparse

mydir = dirname(abspath(__file__))
sslDir = join(mydir, 'ssl')

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
        if hasattr(self, 'httpd') and hasattr(self.httpd, 'shutdown'):
            self.httpd.shutdown()
        self.assertEqual({}, self.reactor._readers)
        self.assertEqual({}, self.reactor._writers)
        self.assertEqual({}, self.reactor._suspended)
        self.assertEqual({}, self.reactor._processes)
        for t in self.reactor._timers:
            cb = t.callback
            code = cb.__code__
            print('WARNING: dangling timer in reactor. Remaining timout: %s with callback to %s() in %s at line %s.' \
                % (t.time-t0, cb.__name__, code.co_filename, code.co_firstlineno))
        self.assertEqual([], self.reactor._timers)
        self.reactor.shutdown()
        self.mockreactor.shutdown()
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
        return self.send(host, port, b'GET %(path)s HTTP/1.0\r\n\r\n' % locals())

    def httpPost(self, host='localhost', port=None, path='/', data='', contentType='text/plain'):
        return self.send(host, port or self.port,
            ('POST %s HTTP/1.0\r\n' % path +
            'Content-Type: %s; charset=\"utf-8\"\r\n' % contentType +
            'Content-Length: %s\r\n' % len(data) +
            '\r\n' +
            data).encode())

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
        thread.daemon = True
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

    def referenceHttpServer(self, port, request, ssl=False, streamingData=None):
        def server(httpd):
            try:
                httpd.serve_forever(poll_interval=0.05)
            finally:
                httpd.shutdown()
        class Handler(BaseHTTPRequestHandler):
            def log_message(*args, **kwargs):
                pass

            def do_GET(self, *args, **kwargs):
                request.append({
                    'command': self.command,
                    'path': self.path,
                    'headers': self.headers})
                self.send_response(200, "OK")
                self.end_headers()

                if not streamingData:
                    self.wfile.write(b'GET RESPONSE')
                    self.wfile.flush()
                    return

                for dataFragment in streamingData:
                    self.wfile.write(dataFragment.encode())
                    self.wfile.flush()

            def do_POST(self, *args, **kwargs):
                request.append({
                    'command': self.command,
                    'path': self.path,
                    'headers': self.headers,
                    'body': self.rfile.read(int(self.headers["Content-Length"]))})
                self.send_response(200, "OK")
                self.end_headers()
                self.wfile.write(b'POST RESPONSE')
                self.wfile.flush()

        if ssl:
            httpd = MySSLTCPServer(("", port), Handler)
        else:
            httpd = TCPServer(("", port), Handler)
        thread=Thread(None, lambda: server(httpd))
        thread.daemon = True
        thread.start()
        return (thread, httpd)

    def proxyServer(self, port, request):
        def server(httpd):
            httpd.serve_forever()
        class Proxy(BaseHTTPRequestHandler):
            def log_message(*args, **kwargs):
                pass

            def do_CONNECT(self):
                request.append({'command': self.command, 'path': self.path, 'headers': self.headers})
                self.send_response(200, "Connection established")
                self.end_headers()
                origRequest = self.connection.recv(4096)
                path = "http://" + self.path + origRequest.split()[1]
                self.wfile.write(urlopen(path).read())
                self.wfile.flush()
                self.connection.close()

        httpd = TCPServer(("", port), Proxy)
        thread=Thread(None, lambda: server(httpd))
        thread.daemon = True
        thread.start()

class MatchAll(object):
    def __eq__(self, other):
        return True
    def __ne__(self, other):
        return False
    def __repr__(self):
        return '*MatchAll*'


class MySSLTCPServer(ThreadingMixIn, TCPServer):
    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        pem = join(sslDir, 'server.pkey')
        cert = join(sslDir, 'server.cert')

        BaseServer.__init__(self, server_address, RequestHandlerClass)
        self.socket = wrap_socket(
                    socket(self.address_family, self.socket_type),
                    server_side=True,
                    certfile=cert,
                    keyfile=pem,
                )

        if bind_and_activate:
            self.server_bind()
            self.server_activate()


class StreamingData(object):
    def __init__(self, data=None, timeout=2.0):
        self._data = data
        self._timeout = timeout
        self._event = Event()

        self._event.clear()

    def __next__(self):
        self._event.wait(timeout=self._timeout)
        if not self._event.is_set():
            raise AssertionError('Timeout reached')
        self._event.clear()
        if not self._data:
            raise StopIteration()
        return self._data.pop(0)

    def __iter__(self):
        return self

    def doNext(self, data=None):
        # Explicitly call .doNext() in tests; typically after end-of-headers.
        if logical_xor(self._data, data):
            if not self._data:
                self._data = [data]
        self._event.set()


def logical_xor(a, b):
    return xor(bool(a), bool(b))


MATCHALL = MatchAll()

