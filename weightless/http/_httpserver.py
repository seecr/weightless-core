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
from StringIO import StringIO
from socket import SHUT_RDWR, error as SocketError, MSG_DONTWAIT
from tempfile import TemporaryFile
from email import message_from_file as parse_mime_message
from zlib import compressobj as deflateCompress
from zlib import decompressobj as deflateDeCompress
from gzip import GzipFile


from OpenSSL import SSL
from random import randint
from time import time
from socket import socket, ssl,  SOL_SOCKET, SO_REUSEADDR, SO_LINGER
from struct import pack
from sys import stdout, getdefaultencoding


RECVSIZE = 4096
CRLF = '\r\n'
CRLF_LEN = 2


class HttpServer(object):
    """Factory that creates a HTTP server listening on port, calling generatorFactory for each new connection.  When a client does not send a valid HTTP request, it is disconnected after timeout seconds. The generatorFactory is called with the HTTP Status and Headers as arguments.  It is expected to return a generator that produces the response -- including the Status line and Headers -- to be send to the client."""

    def __init__(self, reactor, port, generatorFactory, timeout=1, recvSize=RECVSIZE, prio=None, sok=None, maxConnections=None, errorHandler=None, compressResponse=False, bindAddress=None):
        self._reactor = reactor
        self._port = port
        self._bindAddress = bindAddress
        self._generatorFactory = generatorFactory
        self._timeout = timeout
        self._recvSize = recvSize
        self._prio = prio
        self._sok = sok
        self._maxConnections = maxConnections
        self._errorHandler = errorHandler
        self._compressResponse = compressResponse

    def listen(self):
        self._acceptor = Acceptor(
            reactor=self._reactor,
            port=self._port,
            sinkFactory=lambda sok: HttpHandler(
                reactor=self._reactor,
                sok=sok,
                generatorFactory=self._generatorFactory,
                timeout=self._timeout,
                recvSize=self._recvSize,
                prio=self._prio,
                maxConnections=self._maxConnections,
                errorHandler=self._errorHandler,
                compressResponse=self._compressResponse
            ),
            prio=self._prio,
            sok=self._sok,
            bindAddress=self._bindAddress)

    def setMaxConnections(self, m):
        self._maxConnections = m

    def shutdown(self):
        self._acceptor.shutdown()


class HttpsServer(object):
    """Factory that creates a HTTP server listening on port, calling generatorFactory for each new connection.  When a client does not send a valid HTTP request, it is disconnected after timeout seconds. The generatorFactory is called with the HTTP Status and Headers as arguments.  It is expected to return a generator that produces the response -- including the Status line and Headers -- to be send to the client."""

    def __init__(self, reactor, port, generatorFactory, timeout=1, recvSize=RECVSIZE, prio=None, sok=None, certfile='', keyfile='', maxConnections=None, errorHandler=None, compressResponse=False, bindAddress=None):
        self._reactor = reactor
        self._port = port
        self._bindAddress = bindAddress
        self._generatorFactory = generatorFactory
        self._timeout = timeout
        self._recvSize = recvSize
        self._prio = prio
        self._sok = sok
        self._certfile = certfile
        self._keyfile = keyfile
        self._maxConnections = maxConnections
        self._errorHandler = errorHandler
        self._compressResponse = compressResponse

    def listen(self):
        # This should have been a SSLAcceptor ...
        if self._sok == None:
            def verify_cb(conn, cert, errnum, depth, ok):
                # This obviously has to be updated
                print 'Got certificate: %s' % cert.get_subject()
                return ok

            # Initialize context
            ctx = SSL.Context(SSL.SSLv23_METHOD)
            ctx.set_session_id('weightless:%s:%s' % (time(), randint(1024,4096)))
            ctx.set_options(SSL.OP_NO_SSLv2)
            ctx.set_verify(SSL.VERIFY_PEER, verify_cb) # Demand a certificate
            ctx.use_privatekey_file(self._keyfile)
            ctx.use_certificate_file(self._certfile)

            # Set up server
            self._sok = SSL.Connection(ctx, socket())
            self._sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            self._sok.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
            self._sok.bind(('0.0.0.0' if self._bindAddress is None else self._bindAddress, self._port))
            self._sok.listen(127)

        self._acceptor = Acceptor(
            reactor=self._reactor,
            port=self._port,
            sinkFactory=lambda sok: HttpsHandler(
                reactor=self._reactor,
                sok=sok,
                generatorFactory=self._generatorFactory,
                timeout=self._timeout,
                recvSize=self._recvSize,
                prio=self._prio,
                maxConnections=self._maxConnections,
                errorHandler=self._errorHandler,
                compressResponse=self._compressResponse
            ),
            prio=self._prio,
            sok=self._sok,
            bindAddress=self._bindAddress)

    def setMaxConnections(self, m):
        self._maxConnections = m

    def shutdown(self):
        self._acceptor.shutdown()


from sys import stdout
from resource import getrlimit, RLIMIT_NOFILE

def maxFileDescriptors():
    softLimit, hardLimit = getrlimit(RLIMIT_NOFILE)
    return softLimit

def defaultErrorHandler(**kwargs):
    yield 'HTTP/1.0 503 Service Unavailable\r\n\r\n<html><head></head><body><h1>Service Unavailable</h1></body></html>'

def parseContentEncoding(headerValue):
    return [x.strip().lower() for x in headerValue.split(',')]

def parseAcceptEncoding(headerValue):
    result = []
    for encodingMaybeQValue in (v.strip() for v in headerValue.split(',') if v):
        _splitted = encodingMaybeQValue.split(';')
        encoding = _splitted[0]
        if len(_splitted) == 1:
            qvalue = 1.0
        else:
            for acceptParam in _splitted[1:]:
                pName, pValue = acceptParam.split('=', 1)
                if pName == 'q':
                    qvalue = float(pValue)
                    break
                else:
                    encoding += ';' + acceptParam  # media-range

        if qvalue > 0.0001:
            result.append((encoding, qvalue))

    result.sort(key=lambda o: o[1], reverse=True)
    return [o[0] for o in result]


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
    _body = headers[matchEnd:]

    notAbsents = requireAbsent.intersection(set(headersDict.keys()))
    if notAbsents:
        raise ValueError('Response headers contained disallowed items: %s' % ', '.join(notAbsents))

    for header in removeHeaders:
        headerRe = _removeHeaderReCache.get(header, None)
        if headerRe is None:
            
            headerRe = re.compile(r'\r\n%s:.*?\r\n' % re.escape(header), flags=re.I)
            _removeHeaderReCache[header] = headerRe
        _headers = headerRe.sub(CRLF, _headers, count=1)

    for header, value in addHeaders.items():
        _headers += '%s: %s\r\n' % (header, value)

    return _statusLine + _headers + CRLF, _body


class GzipCompress(object):
    def __init__(self):
        self._buffer = StringIO()
        self._gzipFileObj = GzipFile(filename=None, mode='wb', compresslevel=6, fileobj=self._buffer)

    def compress(self, data):
        self._gzipFileObj.write(data)
        return ''

    def flush(self):
        self._gzipFileObj.close()
        return self._buffer.getvalue()


class GzipDeCompress(object):
    def __init__(self):
        self._decompressObj = deflateDeCompress()

    def decompress(self, data):
        return self._decompressObj.decompress(data, 48)  # wbits=16+32; decompress gzip-stream only

    def flush(self):
        return self._decompressObj.flush()

# (De)compression-objects must support: compress / decompress and argumentless flush
SUPPORTED_CONTENT_ENCODINGS = {
    'deflate': {
        'encode': deflateCompress,
        'decode': deflateDeCompress,
     },
    'x-deflate': {
        'encode': deflateCompress,
        'decode': deflateDeCompress,
     },
    'gzip': {
        'encode': GzipCompress,
        'decode': GzipDeCompress,
    },
    'x-gzip': {
        'encode': GzipCompress,
        'decode': GzipDeCompress,
    },
}

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


    def __call__(self):
        part = self._sok.recv(self._recvSize)
        if not part:
            # SOCKET CLOSED by PEER
            self._badRequest()
            return
        self._dataBuffer += part
        self._resetTimer()
        self._dealWithCall()

    def setCallDealer(self, aMethod):
        self._dealWithCall = aMethod
        self._dealWithCall()

    def _readHeaders(self):
        match = REGEXP.REQUEST.match(self._dataBuffer)
        if not match:
            return # for more data
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
            return self._finalize(self._errorHandler)
        if self.request['Method'] == 'POST':
            self.setCallDealer(self._readBody)
        else:
            self.finalize()

    def _readMultiForm(self, boundary):
        # TS: Compression & chunked mode not supported yet
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

    def _processFilename(self, filename):
        parts = filename.split('\\')
        if len(parts) == 1:
            return filename
        return parts[-1]

    def _resetTimer(self):
        if self._timer:
            self._reactor.removeTimer(self._timer)
        self._timer = self._reactor.addTimer(self._timeout, self._badRequest)

    def _readBody(self):
        # Determine Content-Encoding in request, if any.
        if self._decodeRequestBody is None and 'Content-Encoding' in self.request['Headers']:
            contentEncoding = parseContentEncoding(self.request['Headers']['Content-Encoding'])
            if len(contentEncoding) != 1 or contentEncoding[0] not in SUPPORTED_CONTENT_ENCODINGS:
                self._badRequest()
                return
            contentEncoding = contentEncoding[0]

            self._decodeRequestBody = SUPPORTED_CONTENT_ENCODINGS[contentEncoding]['decode']()

        # Chunked - means HTTP/1.1
        if 'Transfer-Encoding' in self.request['Headers'] and self.request['Headers']['Transfer-Encoding'] == 'chunked':
            return self.setCallDealer(self._readChunk)

        # Not chunked
        if 'Content-Length' not in self.request['Headers']:
            return self.finalize()

        contentLength = int(self.request['Headers']['Content-Length'])

        if len(self._dataBuffer) < contentLength:
            return

        if self._decodeRequestBody is not None:
            self.request['Body'] = self._decodeRequestBody.decompress(self._dataBuffer)
            self.request['Body'] += self._decodeRequestBody.flush()
        else:
            self.request['Body'] = self._dataBuffer

        self.finalize()

    def _readChunk(self):
        match = REGEXP.CHUNK_SIZE_LINE.match(self._dataBuffer)
        if not match:
            return # for more data
        self._chunkSize = int(match.groupdict()['ChunkSize'], 16)
        self._dataBuffer = self._dataBuffer[match.end():]
        self.setCallDealer(self._readChunkBody)

    def _readChunkBody(self):
        if self._chunkSize == 0:
            if self._decodeRequestBody is not None:
                self.request['Body'] += self._decodeRequestBody.flush()
            return self.finalize()

        if len(self._dataBuffer) < self._chunkSize + CRLF_LEN:
            return # for more data
        if self._decodeRequestBody is not None:
            self.request['Body'] += self._decodeRequestBody.decompress(self._dataBuffer[:self._chunkSize])
        else:
            self.request['Body'] += self._dataBuffer[:self._chunkSize]
        self._dataBuffer = self._dataBuffer[self._chunkSize + CRLF_LEN:]
        self.setCallDealer(self._readChunk)

    def _determineContentEncoding(self):
        if 'Accept-Encoding' not in self.request['Headers']:
            return None
        acceptEncodings = parseAcceptEncoding(self.request['Headers']['Accept-Encoding'])
        for encoding in acceptEncodings:
            if encoding in SUPPORTED_CONTENT_ENCODINGS:
                return encoding
        return None

    def _finalize(self, finalizeMethod):
        del self.request['_headers']

        encoding = None
        if self._compressResponse == True:
            encoding = self._determineContentEncoding()

        self.request['Client'] = self._sok.getpeername()
        self._handler = finalizeMethod(**self.request)
        if self._timer:
            self._reactor.removeTimer(self._timer)
        self._reactor.removeReader(self._sok)
        self._reactor.addWriter(self._sok, self._writeResponse(encoding=encoding).next, prio=self._prio)

    def finalize(self):
        self._finalize(self._generatorFactory)

    def _badRequest(self):
        self._sok.send('HTTP/1.0 400 Bad Request\r\n\r\n')
        self._reactor.removeReader(self._sok)
        self._sok.shutdown(SHUT_RDWR)
        self._sok.close()

    @identify
    def _writeResponse(self, encoding=None):
        this = yield
        endHeader = False
        headers = ''
        encodeResponseBody = SUPPORTED_CONTENT_ENCODINGS[encoding]['encode']() if encoding is not None else None
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
                            try:
                                _statusLineAndHeaders, _bodyStart = updateResponseHeaders(
                                        headers, match,
                                        addHeaders={'Content-Encoding': encoding},
                                        removeHeaders=['Content-Length'],
                                        requireAbsent=['Content-Encoding'])
                            except ValueError:
                                # Don't interfere with an existing content-encoding
                                encodeResponseBody = None
                                data = headers
                            else:
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
                        yield
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
            self._closeConnection()
        else:
            self._dataBuffer += part
            self._resetTimer()
            self._dealWithCall()

    def _closeConnection(self):
        self._reactor.cleanup(self._sok)

        try:
            self._sok.shutdown()  # No self._sok.shutdown(SHUT_RDWR) for some reason
        except SocketError, e:
            code, message = e.args
            if code == 107:
                pass # KVS: not well understood, not tested. It seems some quick (local) servers close the connection before this point is reached. It may happen more generally. In any case, it is based on a truely existing phenomomon
            else:
                raise
        self._sok.close()

