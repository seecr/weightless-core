## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2007 Seek You Too B.V. (CQ2) http://www.cq2.nl
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
from socket import socket, SHUT_RDWR
from urlparse import urlsplit
from weightless.http import REGEXP, FORMAT, HTTP, parseHeaders
import sys

class HttpReader(object):

    RECVSIZE = 4096

    def __init__(self, reactor, url, callback, errorHandler=None, timeout=1):
        scheme, host, path, query, fragment = urlsplit(url)
        port = '80'
        if ':' in host:
            host, port = host.split(':')
        path = path or '/'
        self._responseBuffer = ''
        self._restData = None
        self._callback = callback
        self._sok = socket()
        self._sok.connect((host, int(port)))
        self._reactor = reactor
        self._reactor.addWriter(self._sok, lambda: self._sendRequest(path, host))
        self._errorHandler = errorHandler or self._defaultErrorHandler
        self._timer = None
        self._timeOuttime = timeout

    def _defaultErrorHandler(self, msg):
        sys.stderr.write(msg)

    def _sendRequest(self, path, host):
        sent = self._sok.send(
            FORMAT.RequestLine % {'Method': 'GET', 'Request_URI': path}
            + FORMAT.HostHeader % {'Host': host}
            + FORMAT.UserAgentHeader
            + HTTP.CRLF)
        self._reactor.removeWriter(self._sok)
        self._reactor.addReader(self._sok, self._headerFragment)

    def _headerFragment(self):
        self._responseBuffer += self._sok.recv(HttpReader.RECVSIZE)
        match = REGEXP.RESPONSE.match(self._responseBuffer)
        if not match:
            if not self._timer:
                self._timer = self._reactor.addTimer(self._timeOuttime, self._timeOut)
            return #for more data
        if self._timer:
            self._reactor.removeTimer(self._timer)
            self._timer = None
        if match.end() < len(self._responseBuffer):
            self._restData = self._responseBuffer[match.end():]
        response = match.groupdict()
        response['Headers'] = parseHeaders(response['_headers'])
        del response['_headers']
        response['Client'] = self._sok.getpeername()
        self._callback(self, **response)

    def _timeOut(self):
        try:
            self._errorHandler('timeout while receiving headers')
        finally:
            self._reactor.removeReader(self._sok)
            self._sok.shutdown(SHUT_RDWR)
            self._sok.close()

    def receiveFragment(self, callback):
        if self._restData:
            callback(self._restData)
            self._restData = None
        self._callback = callback
        self._reactor.removeReader(self._sok)
        self._reactor.addReader(self._sok, self._bodyFragment)

    def _bodyFragment(self):
        fragment = self._sok.recv(HttpReader.RECVSIZE)
        if not fragment:
            self._reactor.removeReader(self._sok)
            self._sok.close()
            self._callback(None)
        else:
            self._callback(fragment)
