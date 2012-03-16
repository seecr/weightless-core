# -*- coding: utf-8 -*-
## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
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

from _acceptor import Acceptor
from weightless.core import identify, Yield
from weightless.http import REGEXP, FORMAT, parseHeaders, parseHeader

import re
from socket import SHUT_RDWR, error as SocketError, MSG_DONTWAIT
from tempfile import TemporaryFile
from email import message_from_file as parse_mime_message
from zlib import compressobj as deflateCompress
from zlib import decompressobj as deflateDeCompress


from OpenSSL import SSL
from random import randint
from time import time
from socket import socket, ssl,  SOL_SOCKET, SO_REUSEADDR, SO_LINGER
from struct import pack
from sys import stdout, getdefaultencoding


RECVSIZE = 4096
CRLF_LEN = 2


class HttpServer(object):
    """Factory that creates a HTTP server listening on port, calling generatorFactory for each new connection.  When a client does not send a valid HTTP request, it is disconnected after timeout seconds. The generatorFactory is called with the HTTP Status and Headers as arguments.  It is expected to return a generator that produces the response -- including the Status line and Headers -- to be send to the client."""
    def __init__(self, reactor, port, generatorFactory, timeout=1, recvSize=RECVSIZE, prio=None, sok=None, maxConnections=None, errorHandler=None, compressResponse=False):
        self._reactor = reactor
        self._port = port
        self._generatorFactory = generatorFactory
        self._timeout = timeout
        self._recvSize = recvSize
        self._prio = prio
        self._sok = sok
        self._maxConnections = maxConnections
        self._errorHandler = errorHandler
        self._compressResponse = compressResponse

    def listen(self):
        self._acceptor = Acceptor(self._reactor, self._port, 
                lambda sok: HttpHandler(self._reactor, sok, self._generatorFactory, self._timeout, 
                    self._recvSize, prio=self._prio, maxConnections=self._maxConnections, 
                    errorHandler=self._errorHandler,
                    compressResponse=self._compressResponse),
                prio=self._prio, sok=self._sok)


    def setMaxConnections(self, m):
        self._maxConnections = m

    def shutdown(self):
        self._acceptor.shutdown()

def HttpsServer(reactor, port, generatorFactory, timeout=1, recvSize=RECVSIZE, prio=None, sok=None, maxConnections=None, errorHandler=None, compressResponse=False, certfile='', keyfile=''):
    """Factory that creates a HTTP server listening on port, calling generatorFactory for each new connection.  When a client does not send a valid HTTP request, it is disconnected after timeout seconds. The generatorFactory is called with the HTTP Status and Headers as arguments.  It is expected to return a generator that produces the response -- including the Status line and Headers -- to be send to the client."""
    if sok == None:
        def verify_cb(conn, cert, errnum, depth, ok):
            # This obviously has to be updated
            print 'Got certificate: %s' % cert.get_subject()
            return ok

        # Initialize context
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.set_session_id('weightless:%s:%s' % (time(), randint(1024,4096)))
        ctx.set_options(SSL.OP_NO_SSLv2)
        ctx.set_verify(SSL.VERIFY_PEER, verify_cb) # Demand a certificate
        ctx.use_privatekey_file (keyfile)
        ctx.use_certificate_file(certfile)

        # Set up server
        sok = SSL.Connection(ctx, socket())
        sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sok.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
        sok.bind(('0.0.0.0', port))
        sok.listen(127)

    return Acceptor(reactor, port, lambda s: HttpsHandler(reactor, s, generatorFactory, timeout, recvSize, prio=prio, maxConnections=maxConnections, errorHandler=errorHandler, compressResponse=compressResponse), prio=prio, sok=sok)

from sys import stdout
from resource import getrlimit, RLIMIT_NOFILE

def maxFileDescriptors():
    softLimit, hardLimit = getrlimit(RLIMIT_NOFILE)
    return softLimit

def defaultErrorHandler(**kwargs):
    yield 'HTTP/1.0 503 Service Unavailable\r\n\r\n<html><head></head><body><h1>Service Unavailable</h1></body></html>'

def parseContentEncoding(headerValue):
    # TS: May there be multi-valued ??, contradiction available.
    return [x.strip().lower() for x in headerValue.split(',')]

def parseAcceptEncoding(headerValue):
    return [x.strip().lower().split(';', 1)[0] for x in [v.strip() for v in headerValue.split(',')] if x]


_removeHeaderReCache = {}
CONTENT_LENGTH_RE = re.compile(r'\r\nContent-Length:.*?\r\n', flags=re.I)
def updateResponseHeaders(headers, match, addHeaders=None, removeHeaders=None, requireAbsent=None):
    requireAbsent = set(requireAbsent or [])
    addHeaders = addHeaders or {}
    removeHeaders = removeHeaders or []
    headersDict = parseHeaders(match.groupdict()['_headers'])

    matchStartHeaders = match.start('_headers')
    matchEnd = match.end()
    _statusLine = headers[:matchStartHeaders - CRLF_LEN]
    _headers = headers[matchStartHeaders - CRLF_LEN:matchEnd - CRLF_LEN]
    _headerToBodySep = '\r\n'
    _body = headers[matchEnd:]

    notAbsents = requireAbsent.intersection(set(headersDict.keys()))
    if notAbsents:
        raise ValueError('Response headers contained disallowed items: %s' % ', '.join(notAbsents))

    for header in removeHeaders:
        headerRe = _removeHeaderReCache.get(header, None)
        if headerRe is None:
            
            headerRe = re.compile(r'\r\n%s:.*?\r\n' % re.escape(header), flags=re.I)
            _removeHeaderReCache[header] = headerRe
        _headers = headerRe.sub('\r\n', _headers, count=1)

    for header, value in addHeaders.items():
        _headers += '%s: %s\r\n' % (header, value)

    return _statusLine + _headers + _headerToBodySep, _body


class HttpHandler(object):
    def __init__(self, reactor, sok, generatorFactory, timeout, recvSize=RECVSIZE, prio=None, maxConnections=None, errorHandler=None, compressResponse=False):
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
        self._prio = prio
        self._window = ''
        self._maxConnections = maxConnections if maxConnections else maxFileDescriptors()
        self._errorHandler = errorHandler if errorHandler else defaultErrorHandler
        self._defaultEncoding = getdefaultencoding()

        self._compressResponse = compressResponse
        self._decodeRequestBody = None
        self._encodeResponseBody = None

        # objects must support: compress / decompress and argumentless flush
        _deflateCompress = deflateCompress
        _deflateDeCompress = deflateDeCompress
        self._supportedContentEncodings = {
                'deflate': {
                    'encode': _deflateCompress,
                    'decode': _deflateDeCompress,
                 },
                'x-deflate': {
                    'encode': _deflateCompress,
                    'decode': _deflateDeCompress,
                 },
        }

    def __call__(self):
        part = self._sok.recv(self._recvSize)
        if not part:
            # SOCKET CLOSED by PEER
            self._badRequest()
            return
        self._dataBuffer += part
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
        if 'Content-Type' in self.request['Headers']:
            cType, pDict = parseHeader(self.request['Headers']['Content-Type'])
            if cType.startswith('multipart/form-data'):
                self._tempfile = TemporaryFile('w+b')
                #self._tempfile = open('/tmp/mimetest', 'w+b')
                self._tempfile.write('Content-Type: %s\r\n\r\n' % self.request['Headers']['Content-Type'])
                self.setCallDealer(lambda: self._readMultiForm(pDict['boundary']))
                return
        if 'Expect' in self.request['Headers']:
            self._sok.send('HTTP/1.1 100 Continue\r\n\r\n')

        if self._reactor.getOpenConnections() > self._maxConnections:
            self.request['ResponseCode'] = 503
            self._finalize(self._errorHandler)
        else:
            self.setCallDealer(self._readBody)

    def _readMultiForm(self, boundary):
        # TS: Compression & chunked mode not supported yet
        if self._timer:
            self._reactor.removeTimer(self._timer)
            self._timer = None
        self._tempfile.write(self._dataBuffer)

        self._window += self._dataBuffer
        self._window = self._window[-2*self._recvSize:]

        if self._window.endswith("\r\n--%s--\r\n" % boundary):
            self._tempfile.seek(0)

            form = {}
            for msg in parse_mime_message(self._tempfile).get_payload():
                cType, pDict = parseHeader(msg['Content-Disposition'])
                contentType = msg.get_content_type()
                fieldName = pDict['name'][1:-1]
                if not fieldName in form:
                    form[fieldName] = []

                if 'filename' in pDict:
                    filename = self._processFilename(pDict['filename'][1:-1])
                    form[fieldName].append((filename, contentType, msg.get_payload()))
                else:
                    form[fieldName].append(msg.get_payload())

            self.request['Form'] = form
            self._tempfile.close()
            self.finalize()
            return

        self._dataBuffer= ''
        if not self._timer:
            self._timer = self._reactor.addTimer(self._timeout, self._badRequest)

    def _processFilename(self, filename):
        parts = filename.split('\\')
        if len(parts) == 1:
            return filename
        return parts[-1]

    def _readBody(self):
        if self.request['Method'] == 'GET':
            self.finalize()
        elif self.request['Method'] == 'POST':
            # Determine Content-Encoding in request, if any.
            if self._decodeRequestBody is None and 'Content-Encoding' in self.request['Headers']:
                contentEncoding = parseContentEncoding(self.request['Headers']['Content-Encoding'])
                if len(contentEncoding) != 1 or contentEncoding[0] not in self._supportedContentEncodings:
                    if self._timer:
                        self._reactor.removeTimer(self._timer)
                        self._timer = None
                    self._badRequest()
                    return
                contentEncoding = contentEncoding[0]

                self._decodeRequestBody = self._supportedContentEncodings[contentEncoding]['decode']()

            # Not chunked
            if 'Content-Length' in self.request['Headers']:
                contentLength = int(self.request['Headers']['Content-Length'])

                if len(self._dataBuffer) < contentLength:
                    if not self._timer:
                        self._timer = self._reactor.addTimer(self._timeout, self._badRequest)
                    return
                if self._timer:
                    self._reactor.removeTimer(self._timer)
                    self._timer = None

                if self._decodeRequestBody is not None:
                    self.request['Body'] = self._decodeRequestBody.decompress(self._dataBuffer)
                    self.request['Body'] += self._decodeRequestBody.flush()
                else:
                    self.request['Body'] = self._dataBuffer
                self.finalize()

            # Chunked - means HTTP/1.1
            elif 'Transfer-Encoding' in self.request['Headers'] and self.request['Headers']['Transfer-Encoding'] == 'chunked':
                self.setCallDealer(self._readChunk)
            else:
                self.finalize()
        else:
            self.finalize()

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
            if self._decodeRequestBody is not None:
                self.request['Body'] += self._decodeRequestBody.flush()
            self.finalize()
        else:
            if len(self._dataBuffer) < self._chunkSize + CRLF_LEN:
                if not self._timer:
                    self._timer = self._reactor.addTimer(self._timeout, self._badRequest)
                return # for more data
            if self._timer:
                self._reactor.removeTimer(self._timer)
                self._timer = None
            if self._decodeRequestBody is not None:
                self.request['Body'] += self._decodeRequestBody.decompress(self._dataBuffer[:self._chunkSize])
            else:
                self.request['Body'] += self._dataBuffer[:self._chunkSize]
            self._dataBuffer = self._dataBuffer[self._chunkSize + CRLF_LEN:]
            self.setCallDealer(self._readChunk)

    def _determineContentEncoding(self):
        if 'Accept-Encoding' not in self.request['Headers']:
            return
        acceptEncodings = set(parseAcceptEncoding(self.request['Headers']['Accept-Encoding']))
        for encoding in sorted(self._supportedContentEncodings.keys()):
            if encoding in acceptEncodings:
                return encoding

    def _finalize(self, finalizeMethod):
        del self.request['_headers']
        if self._compressResponse == True:
            self._encodeResponseBodyStr = self._determineContentEncoding()
            self._encodeResponseBody = self._supportedContentEncodings[self._encodeResponseBodyStr]['encode']()

        self.request['Client'] = self._sok.getpeername()
        self._handler = finalizeMethod(**self.request)
        self._reactor.removeReader(self._sok)
        self._reactor.addWriter(self._sok, self._writeResponse().next, prio=self._prio)

    def finalize(self):
        self._finalize(self._generatorFactory)

    def _badRequest(self):
        self._sok.send('HTTP/1.0 400 Bad Request\r\n\r\n')
        self._reactor.removeReader(self._sok)
        self._sok.shutdown(SHUT_RDWR)
        self._sok.close()

    @identify
    def _writeResponse(self):
        this = yield
        endHeader = False
        headers = ''
        encodeResponseBody = self._encodeResponseBody
        # TODO: set self._encodeResponseBody before, test is not None!
        while True:
            yield
            try:
                if self._rest:
                    data = self._rest
                else:
                    data = self._handler.next()
                    if data is Yield:
                        continue
                    if callable(data):
                        data(self._reactor, this.next)
                        yield
                        data.resumeWriter()
                        continue
                    if type(data) is unicode:
                        data = data.encode(self._defaultEncoding)
                if encodeResponseBody is not None:
                    if endHeader is False:
                        headers += data
                        match = REGEXP.RESPONSE.match(headers)
                        if match:
                            endHeader = True
                            #_header, _bodyStart = updateResponseHeaders(headers, match)
                            try:
                                _statusLineAndHeaders, _bodyStart = updateResponseHeaders(
                                        headers, match,
                                        addHeaders={'Content-Encoding': self._encodeResponseBodyStr},
                                        removeHeaders=['Content-Length'],
                                        requireAbsent=['Content-Encoding'])
                            except ValueError:
                                # Don't interfere with an existing content-encoding
                                encodeResponseBody = None
                                data = headers
                            #_header, _bodyStart = headers.split('\r\n\r\n', 1)
                            #data = _header + '\r\nContent-Encoding: %s\r\n\r\n%s' % (self._encodeResponseBodyStr, encodeResponseBody.compress(_bodyStart))
                            data = _statusLineAndHeaders + encodeResponseBody.compress(_bodyStart)
                        else:
                            continue
                    else:
                        data = encodeResponseBody.compress(data)

                sent = self._sok.send(data, MSG_DONTWAIT)
                if sent < len(data):
                    self._rest = data[sent:]
                else:
                    self._rest = None
            except StopIteration:
                if encodeResponseBody:
                    self._rest = encodeResponseBody.flush()
                    while self._rest:
                        data = self._rest
                        sent = self._sok.send(data, MSG_DONTWAIT)
                        if sent < len(data):
                            self._rest = data[sent:]
                        else:
                            self._rest = None
                self._closeConnection()
                yield
            except:
                self._closeConnection()
                raise

    def _closeConnection(self):
        self._reactor.cleanup(self._sok)

        try:
            self._sok.shutdown(SHUT_RDWR)
        except SocketError, e:
            code, message = e.args
            if code == 107:
                pass # KVS: not well understood, not tested. It seems some quick (local) servers close the connection before this point is reached. It may happen more generally. In any case, it is based on a truely existing phenomomon
            else:
                raise
        self._sok.close()

class HttpsHandler(HttpHandler):
    def __call__(self):
        try:
            part = self._sok.recv(self._recvSize)
            if not part:
                # SOCKET CLOSED by PEER
                self._badRequest()
                return
        except (SSL.WantReadError, SSL.WantWriteError, SSL.WantX509LookupError):
            pass
        except Exception, e:
            self._closeDuringRead()
        else:
            self._dataBuffer += part
            self._dealWithCall()

    def _closeDuringRead(self):
        self._reactor.removeReader(self._sok)
        self._sok.shutdown()
        self._sok.close()

    def _closeConnection(self):
        self._reactor.removeWriter(self._sok)
        self._sok.shutdown()
        self._sok.close()
