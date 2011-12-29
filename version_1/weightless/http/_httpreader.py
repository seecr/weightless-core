## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
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
from socket import socket, SHUT_RDWR, SHUT_WR
from urlparse import urlsplit
from weightless.http import REGEXP, FORMAT, HTTP, parseHeaders
from _bufferedhandler import BufferedHandler

import sys

RECVSIZE = 4096

def soapPost(reactor, serverUrl, soapAction, body, responseCallback=lambda x:None, timeout=15):
    handler = BufferedHandler(HandlerFacade(responseCallback, lambda x: None, [body, None].__iter__))
    host, port, path = _httpParseUrl(serverUrl)
    HttpReader(reactor, Connector(reactor, host, port), handler, "POST", host, path, headers={'SOAPAction': soapAction}, timeout=timeout)

def Connector(reactor, host, port):
    sok = socket()
    sok.connect((host, port))
    return sok

class HandlerFacade(object):
    def __init__(self, responseHandler, errorHandler, bodyHandler):
        self._bodyHandler = bodyHandler and bodyHandler() or xrange(0)
        self.throw = errorHandler
        self.send = responseHandler
    def next(self):
        return self._bodyHandler.next()
    def __iter__(self):
        return self

def _httpParseUrl(url):
    scheme, host, path, query, fragment = urlsplit(url)
    port = '80'
    if ':' in host:
        host, port = host.split(':')
    path = path or '/'
    if query:
        path += '?' + query
    if fragment:
        path += '#' + fragment
    return host, int(port), path

def HttpReaderFacade(reactor, url, responseHandler, errorHandler=None, timeout=1, headers={}, bodyHandler=None, recvSize=RECVSIZE):
    host, port, path = _httpParseUrl(url)
    method = bodyHandler and 'POST' or 'GET'
    return HttpReader(reactor, Connector(reactor, host, int(port)), HandlerFacade(responseHandler, errorHandler, bodyHandler), method, host, path, timeout=timeout,  headers=headers, recvSize=recvSize)

class HttpReader(object):

    def __init__(self, reactor, sokket, handler, method, host, path, headers={}, timeout=1, recvSize=RECVSIZE):
        self._responseBuffer = ''
        self._restData = None
        self._handler = handler
        self._sok = sokket
        self._reactor = reactor
        if method == 'POST':
            requestSendMethod = lambda: self._sendPostRequest(path, host, headers)
        else:
            requestSendMethod = lambda: self._sendGetRequest(path, host)
        self._reactor.addWriter(self._sok, requestSendMethod)
        self._timeOuttime = timeout

        self._timer = self._reactor.addTimer(self._timeOuttime, self._timeOut)
        self._recvSize = recvSize
        self._buffer = ''
        self._peername = self._sok.getpeername()

    def _sendPostRequest(self, path, host, headers):
        headers['Transfer-Encoding'] = 'chunked'
        self._sok.sendall(
            FORMAT.RequestLine % {'Method': 'POST', 'Request_URI': path, 'HTTPVersion':'1.1'}
            + FORMAT.HostHeader % {'Host': host}
            + ''.join(FORMAT.Header % header for header in headers.items())
            + FORMAT.UserAgentHeader
            + HTTP.CRLF)
        item = self._handler.next()
        while item:
            self._sendChunk(item)
            item = self._handler.next()

        self._sendChunk('')
        self._reactor.removeWriter(self._sok)
        self._reactor.addReader(self._sok, self._headerFragment)

    def _createChunk(self, data):
        return hex(len(data))[len('0x'):].upper() + HTTP.CRLF + data + HTTP.CRLF

    def _sendChunk(self, data):
        self._sok.sendall(self._createChunk(data))

    def _sendGetRequest(self, path, host):
        self._sok.sendall(
            FORMAT.RequestLine % {'Method': 'GET', 'Request_URI': path, 'HTTPVersion':'1.1'}
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
                self._startTimer()
            return #for more data
        self._stopTimer()
        if match.end() < len(self._responseBuffer):
            restData = self._responseBuffer[match.end():]
        else:
            restData = ''
        response = match.groupdict()
        response['Headers'] = parseHeaders(response['_headers'])
        self._chunked = 'Transfer-Encoding' in response['Headers'] and response['Headers']['Transfer-Encoding'] == 'chunked'
        del response['_headers']
        response['Client'] = self._peername
        self._handler.send(response)
        if restData:
            self._sendFragment(restData)
        self._reactor.removeReader(self._sok)
        self._reactor.addReader(self._sok, self._bodyFragment)
        self._startTimer()

    def _bodyFragment(self):
        self._stopTimer()
        fragment = self._sok.recv(self._recvSize)

        if not fragment:
            self._stop()
        else:
            self._sendFragment(fragment)
            self._startTimer()

    def _stop(self):
        self._reactor.removeReader(self._sok)
        self._sok.close()
        self._handler.throw(StopIteration())

    def _sendFragment(self, fragment):
        if self._chunked:
            self._buffer += fragment

            match = REGEXP.CHUNK_SIZE_LINE.match(self._buffer)
            if match:
                chunkSize = int("0x" + self._buffer[:match.end()], 16)
                if chunkSize == 0:
                    self._stop()
                    return

                if len(self._buffer) >= chunkSize + match.end():
                    self._buffer = self._buffer[match.end():]
                    data = self._buffer[:chunkSize]
                    self._buffer = self._buffer[chunkSize + len(HTTP.CRLF):]
                    self._handler.send(data)
        else:
            self._handler.send(fragment)

    def _startTimer(self):
        self._timer = self._reactor.addTimer(self._timeOuttime, self._timeOut)

    def _stopTimer(self):
        if self._timer:
            self._reactor.removeTimer(self._timer)
            self._timer = None

    def _timeOut(self):
        try:
            self._handler.throw(Exception('timeout while receiving data'))
        finally:
            self._reactor.removeReader(self._sok)
            self._sok.shutdown(SHUT_RDWR)
            self._sok.close()
