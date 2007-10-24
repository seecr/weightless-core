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

    def __init__(self, reactor, url, responseHandler, errorHandler=None, timeout=1, headers={}, bodyHandler=None, recvSize=RECVSIZE):
        scheme, host, path, query, fragment = urlsplit(url)
        port = '80'
        if ':' in host:
            host, port = host.split(':')
        path = path or '/'
        self._responseBuffer = ''
        self._restData = None
        self._responseHandler = responseHandler
        self._sok = self._createSocket(host, int(port))
        self._reactor = reactor
        if bodyHandler:
            requestSendMethod = lambda: self._sendPostRequest(path, host, headers, bodyHandler)
        else:
            requestSendMethod = lambda: self._sendGetRequest(path, host)
        self._reactor.addWriter(self._sok, requestSendMethod)
        self._errorHandler = errorHandler or self._defaultErrorHandler
        self._timer = None
        self._timeOuttime = timeout
        self._recvSize = recvSize

    def _createSocket(self, host, port):
        sok = socket()
        sok.connect((host, int(port)))
        return sok

    def _defaultErrorHandler(self, msg):
        sys.stderr.write(msg)

    def _sendPostRequest(self, path, host, headers, bodyHandler):
        headers['Transfer-Encoding'] = 'chunked'
        sent = self._sok.send(
            FORMAT.RequestLine % {'Method': 'POST', 'Request_URI': path}
            + FORMAT.HostHeader % {'Host': host}
            + ''.join(FORMAT.Header % header for header in headers.items())
            + FORMAT.UserAgentHeader
            + HTTP.CRLF)
        for item in bodyHandler():
            chunk = self._createChunk(item)
            bytesSent = self._sok.send(chunk)
            assert bytesSent == len(chunk)

        chunk = self._createChunk('')
        bytesSent = self._sok.send(chunk)
        assert bytesSent == len(chunk)

        self._reactor.removeWriter(self._sok)
        self._reactor.addReader(self._sok, self._headerFragment)

    def _createChunk(self, data):
        return hex(len(data))[len('0x'):].upper() + HTTP.CRLF + data + HTTP.CRLF

    def _sendGetRequest(self, path, host):
        sent = self._sok.send(
            FORMAT.RequestLine % {'Method': 'GET', 'Request_URI': path}
            + FORMAT.HostHeader % {'Host': host}
            + FORMAT.UserAgentHeader
            + HTTP.CRLF)
        self._reactor.removeWriter(self._sok)
        self._reactor.addReader(self._sok, self._headerFragment)

    def _headerFragment(self):
        self._responseBuffer += self._sok.recv(self._recvSize)
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
        self._responseHandler(**response)

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
        self._responseHandler = callback
        self._reactor.removeReader(self._sok)
        self._reactor.addReader(self._sok, self._bodyFragment)

    def _bodyFragment(self):
        fragment = self._sok.recv(self._recvSize)
        if not fragment:
            self._reactor.removeReader(self._sok)
            self._sok.close()
            self._responseHandler(None)
        else:
            self._responseHandler(fragment)
