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
from _acceptor import Acceptor
from weightless.http import REGEXP, FORMAT, HTTP, parseHeaders
from socket import SHUT_RDWR, error as SocketError

RECVSIZE = 4096
CRLF_LEN = 2

def HttpServer(reactor, port, generatorFactory, timeout=1, recvSize=RECVSIZE):
    """Factory that creates a HTTP server listening on port, calling generatorFactory for each new connection.  When a client does not send a valid HTTP request, it is disconnected after timeout seconds. The generatorFactory is called with the HTTP Status and Headers as arguments.  It is expected to return a generator that produces the response -- including the Status line and Headers -- to be send to the client."""
    return Acceptor(reactor, port, lambda sok: HttpHandler(reactor, sok, generatorFactory, timeout, recvSize))

class HttpHandler(object):

    def __init__(self, reactor, sok, generatorFactory, timeout, recvSize=RECVSIZE):
        self._reactor = reactor
        self._sok = sok
        self._generatorFactory = generatorFactory
        self._dataBuffer = ''
        self._rest = None
        self._timeout = timeout
        self._timer = None
        self._recvSize = recvSize
        self.request = None
        self._dealWithCall = self._readHeaders

    def __call__(self):
        kwargs = {}
        self._dataBuffer += self._sok.recv(self._recvSize)
        self._dealWithCall()

    def setCallDealer(self, aMethod):
        self._dealWithCall = aMethod
        self._dealWithCall()

    def _readHeaders(self):
        match = REGEXP.REQUEST.match(self._dataBuffer)
        if not match:
            if not self._timer:
                self._timer = self._reactor.addTimer(self._timeout, self._badRequest)
            return # for more data
        if self._timer:
            self._reactor.removeTimer(self._timer)
            self._timer = None
        self.request = match.groupdict()
        self.request['Body'] = ''
        self.request['Headers'] = parseHeaders(self.request['_headers'])
        matchEnd = match.end()
        self._dataBuffer = self._dataBuffer[matchEnd:]
        if 'Expect' in self.request['Headers']:
            self._sok.send('HTTP/1.1 100 Continue\r\n\r\n')
        self.setCallDealer(self._readBody)

    def _readBody(self):
        if self.request['Method'] == 'GET':
            self.finalize()
        elif self.request['Method'] == 'POST':
            if 'Content-Length' in self.request['Headers']:
                contentLength = int(self.request['Headers']['Content-Length'])

                if len(self._dataBuffer) < contentLength:
                    if not self._timer:
                        self._timer = self._reactor.addTimer(self._timeout, self._badRequest)
                    return
                if self._timer:
                    self._reactor.removeTimer(self._timer)
                    self._timer = None

                self.request['Body'] = self._dataBuffer
                self.finalize()
            elif 'Transfer-Encoding' in self.request['Headers'] and self.request['Headers']['Transfer-Encoding'] == 'chunked':
                self.setCallDealer(self._readChunk)

    def _readChunk(self):
        match = REGEXP.CHUNK_SIZE_LINE.match(self._dataBuffer)
        if not match:
            if not self._timer:
                self._timer = self._reactor.addTimer(self._timeout, self._badRequest)
            return # for more data
        if self._timer:
            self._reactor.removeTimer(self._timer)
            self._timer = None
        self._chunkSize = int(match.groupdict()['ChunkSize'], 16)
        self._dataBuffer = self._dataBuffer[match.end():]
        self.setCallDealer(self._readChunkBody)

    def _readChunkBody(self):
        if self._chunkSize == 0:
            self.finalize()
        else:
            if len(self._dataBuffer) < self._chunkSize + CRLF_LEN:
                if not self._timer:
                    self._timer = self._reactor.addTimer(self._timeout, self._badRequest)
                return # for more data
            if self._timer:
                self._reactor.removeTimer(self._timer)
                self._timer = None
            self.request['Body'] += self._dataBuffer[:self._chunkSize]
            self._dataBuffer = self._dataBuffer[self._chunkSize + CRLF_LEN:]
            self.setCallDealer(self._readChunk)

    def finalize(self):
        del self.request['_headers']
        self.request['Client'] = self._sok.getpeername()
        self._handler = self._generatorFactory(**self.request)
        self._reactor.removeReader(self._sok)
        self._reactor.addWriter(self._sok, self._writeResponse)

    def _badRequest(self):
        self._sok.send('HTTP/1.0 400 Bad Request\r\n\r\n')
        self._reactor.removeReader(self._sok)
        self._sok.shutdown(SHUT_RDWR)
        self._sok.close()

    def _writeResponse(self):
        try:
            if self._rest:
                data = self._rest
            else:
                data = self._handler.next()
            sent = self._sok.send(data)
            if sent < len(data):
                self._rest = data[sent:]
            else:
                self._rest = None
        except StopIteration:
            self._reactor.removeWriter(self._sok)
            self._sok.shutdown(SHUT_RDWR)
            #try:
                #self._sok.shutdown(SHUT_RDWR)
            #except SocketError, e:
                #code, message = e.args
                #if code == 107:
                    #pass # KVS: not well understood, not tested. It seems some quick (local) servers close the connection before this point is reached. It may happen more generally.
                #else:
                    #raise
            self._sok.close()
