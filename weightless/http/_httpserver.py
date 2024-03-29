# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2014-2015, 2018-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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

from ._acceptor import Acceptor
from weightless.core import identify, Yield, compose
from weightless.http import REGEXP, parseHeaders, parseHeaderFieldvalue

import re
from resource import getrlimit, RLIMIT_NOFILE
from socket import SHUT_RDWR, error as SocketError, MSG_DONTWAIT
from tempfile import TemporaryFile
from traceback import print_exception
from email import message_from_binary_file
from zlib import compressobj as deflateCompress
from zlib import decompressobj as deflateDeCompress
from zlib import Z_DEFAULT_COMPRESSION, DEFLATED, MAX_WBITS, DEF_MEM_LEVEL, Z_DEFAULT_STRATEGY

from sys import getdefaultencoding, exc_info
import sys

RECVSIZE = 4096
CRLF = b'\r\n'
CRLF_LEN = 2


class HttpServer(object):
    """Factory that creates a HTTP server listening on port, calling generatorFactory for each new connection.  When a client does not send a valid HTTP request, it is disconnected after timeout seconds. The generatorFactory is called with the HTTP Status and Headers as arguments.  It is expected to return a generator that produces the response -- including the Status line and Headers -- to be send to the client."""

    def __init__(self, reactor, port, generatorFactory, timeout=1, recvSize=RECVSIZE, prio=None, sok=None, maxConnections=None, errorHandler=None, compressResponse=False, bindAddress=None, socketWrapper=None):
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
        self._socketWrapper = socketWrapper

    def listen(self):
        self._acceptor = Acceptor(
            reactor=self._reactor,
            port=self._port,
            sinkFactory=lambda sok: HttpHandler(
                reactor=self._reactor,
                sok=sok if self._socketWrapper is None else self._socketWrapper(sok),
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



def maxFileDescriptors():
    softLimit, hardLimit = getrlimit(RLIMIT_NOFILE)
    return softLimit

def defaultErrorHandler(**kwargs):
    yield 'HTTP/1.0 503 Service Unavailable\r\n\r\n<html><head></head><body><h1>Service Unavailable</h1></body></html>'

def parseContentEncoding(headerValue):
    return [x.strip().lower() for x in headerValue.split(b',')]

def parseAcceptEncoding(headerValue):
    result = []
    for encodingMaybeQValue in (v.strip() for v in headerValue.split(b',') if v):
        _splitted = encodingMaybeQValue.split(b';')
        encoding = _splitted[0]
        if len(_splitted) == 1:
            qvalue = 1.0
        else:
            for acceptParam in _splitted[1:]:
                pName, pValue = acceptParam.split(b'=', 1)
                if pName == b'q':
                    qvalue = float(pValue)
                    break
                else:
                    encoding += b';' + acceptParam  # media-range

        if qvalue > 0.0001:
            result.append((encoding, qvalue))

    result.sort(key=lambda o: o[1], reverse=True)
    return [o[0] for o in result]


_removeHeaderReCache = {}
#CONTENT_LENGTH_RE = re.compile(r'\r\nContent-Length:.*?\r\n', flags=re.I)
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
        raise ValueError('Response headers contained disallowed items: {}'.format(', '.join(each.decode() for each in notAbsents)))

    for header in removeHeaders:
        headerRe = _removeHeaderReCache.get(header, None)
        if headerRe is None:
            headerRe = re.compile(b'\r\n' + re.escape(header) + b':.*?\r\n', flags=re.I)
            _removeHeaderReCache[header] = headerRe
        _headers = headerRe.sub(CRLF, _headers, count=1)

    for header, value in list(addHeaders.items()):
        _headers += header+b": "+value + CRLF
    return _statusLine + _headers + CRLF, _body


class GzipCompress(object):
    def __init__(self):
        # See for more info:
        #   - zlib's zlib.h deflateInit2 comment
        #   - Python sources: Modules/zlibmodule.c PyZlib_compressobj
        # compressobj([level[, method[, wbits[, memlevel[, strategy]]]]])
        self._compressObj = deflateCompress(Z_DEFAULT_COMPRESSION, DEFLATED, MAX_WBITS+16, DEF_MEM_LEVEL, Z_DEFAULT_STRATEGY)  # wbits=15+16; "The default value is 15 ..." "windowBits can also be greater than 15 for optional gzip encoding.  Add 16 to windowBits to write a simple gzip header and trailer around the compressed data instead of a zlib wrapper."

    def compress(self, data):
        return self._compressObj.compress(data)

    def flush(self):
        return self._compressObj.flush()


class GzipDeCompress(object):
    def __init__(self):
        # See for more info:
        #   - zlib's zlib.h inflateInit2 comment
        #   - Python sources: Modules/zlibmodule.c PyZlib_decompressobj
        self._decompressObj = deflateDeCompress(MAX_WBITS+16)  # wbits=15+16; "The default value is 15 ..." "... windowBits can also be greater than 15 for optional gzip decoding. ..." "... or add 16 to decode only the gzip format"

    def decompress(self, data):
        return self._decompressObj.decompress(data)

    def flush(self):
        return self._decompressObj.flush()

# (De)compression-objects must support: compress / decompress and argumentless flush
SUPPORTED_COMPRESSION_CONTENT_ENCODINGS = {
    b'deflate': {
        'encode': deflateCompress,
        'decode': deflateDeCompress,
     },
    b'x-deflate': {
        'encode': deflateCompress,
        'decode': deflateDeCompress,
     },
    b'gzip': {
        'encode': GzipCompress,
        'decode': GzipDeCompress,
    },
    b'x-gzip': {
        'encode': GzipCompress,
        'decode': GzipDeCompress,
    },
}

class HttpHandler(object):
    def __init__(self, reactor, sok, generatorFactory, timeout, recvSize=RECVSIZE, prio=None, maxConnections=None, errorHandler=None, compressResponse=False):
        self._reactor = reactor
        self._sok = sok
        self._generatorFactory = generatorFactory
        self._dataBuffer = b''
        self._rest = None
        self._timeout = timeout
        self._timer = None
        self._recvSize = recvSize
        self.request = None
        self._dealWithCall = self._readHeaders
        self._prio = prio
        self._window = b''
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
        self.request['Body'] = b''
        self.request['Headers'] = parseHeaders(self.request['_headers'])
        matchEnd = match.end()
        self._dataBuffer = self._dataBuffer[matchEnd:]
        if b'Content-Type' in self.request['Headers']:
            cType, pDict = parseHeaderFieldvalue(self.request['Headers'][b'Content-Type'])
            if cType.startswith(b'multipart/form-data'):
                self._tempfile = TemporaryFile('w+b')
                #self._tempfile = open('/tmp/mimetest', 'w+b')
                self._tempfile.write(b'Content-Type: %s\r\n\r\n' % self.request['Headers'][b'Content-Type'])
                self.setCallDealer(lambda: self._readMultiForm(pDict[b'boundary']))
                return
        if b'Expect' in self.request['Headers']:
            self._sok.send(b'HTTP/1.1 100 Continue\r\n\r\n')

        if self._reactor.getOpenConnections() > self._maxConnections:
            self.request['ResponseCode'] = 503
            return self._finalize(self._errorHandler)
        if self.request['Method'] in [b'POST', b'PUT']:
            self.setCallDealer(self._readBody)
        else:
            self.finalize()

    def _readMultiForm(self, boundary):
        # TS: Compression & chunked mode not supported yet
        self._tempfile.write(self._dataBuffer)

        self._window += self._dataBuffer
        self._window = self._window[-2*self._recvSize:]

        if self._window.endswith(b"\r\n--%s--\r\n" % boundary):
            self._tempfile.seek(0)

            form = {}
            for msg in message_from_binary_file(self._tempfile).get_payload():
                cType, pDict = parseHeaderFieldvalue(msg['Content-Disposition'].encode())
                contentType = msg.get_content_type()
                fieldName = str(pDict[b'name'], encoding='utf-8')
                if b'filename' in pDict:
                    filename = self._processFilename(pDict[b'filename'])
                    form.setdefault(fieldName, []).append((filename, contentType, msg.get_payload(decode=True)))
                else:
                    form.setdefault(fieldName, []).append(msg.get_payload())

            self.request['Form'] = form
            self._tempfile.close()
            self.finalize()
            return

        self._dataBuffer= b''

    def _processFilename(self, filename):
        parts = filename.split(b'\\')
        return str(filename if len(parts) == 1 else parts[-1], encoding='utf-8')

    def _resetTimer(self):
        if self._timer:
            self._reactor.removeTimer(self._timer)
        self._timer = self._reactor.addTimer(self._timeout, self._badRequest)

    def _readBody(self):
        # Determine Content-Encoding in request, if any.
        if self._decodeRequestBody is None and b'Content-Encoding' in self.request['Headers']:
            contentEncoding = parseContentEncoding(self.request['Headers'][b'Content-Encoding'])
            if len(contentEncoding) != 1 or contentEncoding[0] not in SUPPORTED_COMPRESSION_CONTENT_ENCODINGS:
                self._badRequest()
                return
            contentEncoding = contentEncoding[0]

            self._decodeRequestBody = SUPPORTED_COMPRESSION_CONTENT_ENCODINGS[contentEncoding]['decode']()

        # Chunked - means HTTP/1.1
        if b'Transfer-Encoding' in self.request['Headers'] and self.request['Headers'][b'Transfer-Encoding'] == b'chunked':
            return self.setCallDealer(self._readChunk)

        # Not chunked
        if b'Content-Length' not in self.request['Headers']:
            return self.finalize()

        contentLength = int(self.request['Headers'][b'Content-Length'])
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
        if b'Accept-Encoding' not in self.request['Headers']:
            return None
        acceptEncodings = parseAcceptEncoding(self.request['Headers'][b'Accept-Encoding'])
        for encoding in acceptEncodings:
            if encoding in SUPPORTED_COMPRESSION_CONTENT_ENCODINGS:
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
        self._reactor.addWriter(self._sok, self._writeResponse(encoding=encoding).__next__, prio=self._prio)

    def finalize(self):
        self._finalize(self._generatorFactory)

    def _badRequest(self):
        self._sok.send(b'HTTP/1.0 400 Bad Request\r\n\r\n')
        self._reactor.removeReader(self._sok)
        self._sok.shutdown(SHUT_RDWR)
        self._sok.close()

    def _send(self, data):
        if type(data) != bytes:
            data = data.encode()
        try:
            sent = self._sok.send(data, MSG_DONTWAIT)
            if sent < len(data):
                self._rest = data[sent:]
            else:
                self._rest = None
        except Exception:
            original_exc = exc_info()
            if data and type(data) is bytes:
                sys.stderr.write('Error while sending data "{0} ..."\n'.format(data[:120]))
                sys.stderr.flush()
            try:
                self._handler.throw(*original_exc)
            except StopIteration:
                pass
            self._closeConnection()
            raise original_exc[0](original_exc[1]).with_traceback(original_exc[2])

    @identify
    @compose
    def _writeResponse(self, encoding=None):
        this = yield
        endHeader = False
        responseStarted = False
        headers = b''
        encodeResponseBody = SUPPORTED_COMPRESSION_CONTENT_ENCODINGS[encoding]['encode']() if encoding is not None else None

        data = None

        def _no_response_500(msg):
            self._rest = b'HTTP/1.0 500 Internal Server Error\r\n\r\n'
            while self._rest:
                yield
                data = self._rest
                self._send(data)
                sys.stderr.write(msg)

        while True:
            yield
            if self._rest:
                data = self._rest
            else:
                try:
                    data = next(self._handler)
                except (AssertionError, SystemExit, KeyboardInterrupt):
                    raise
                except StopIteration:
                    if encodeResponseBody:
                        self._rest = encodeResponseBody.flush()
                        while self._rest:
                            yield
                            data = self._rest
                            responseStarted = True
                            self._send(data)

                    if not responseStarted:
                        yield _no_response_500(msg='Error in handler - no response sent, 500 given.\n')

                    self._closeConnection()
                    yield
                except Exception:
                    original_exc = exc_info()
                    if responseStarted:
                        sys.stderr.write('Error in handler - after response started:\n')
                    else:
                        yield _no_response_500(msg='Error in handler - no response sent, 500 given:\n')

                    print_exception(*original_exc)
                    sys.stderr.flush()
                    self._closeConnection()
                    yield

                if data is Yield:
                    continue
                if callable(data):
                    data(self._reactor, this.__next__)
                    yield
                    data.resumeWriter()
                    continue
                if isinstance(data, str):
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
                                    addHeaders={b'Content-Encoding': encoding},
                                    removeHeaders=[b'Content-Length'],
                                    requireAbsent=[b'Content-Encoding'])
                        except ValueError:
                            # Don't interfere with an existing content-encoding
                            encodeResponseBody = None
                            data = headers
                        else:
                            data = _statusLineAndHeaders + encodeResponseBody.compress(_bodyStart)
                    else:
                        continue
                elif not self._rest:
                    data = encodeResponseBody.compress(data)
            if data:
                responseStarted = True
                self._send(data)

    def _closeConnection(self):
        self._handler.close()
        self._reactor.cleanup(self._sok)

        try:
            self._sok.shutdown(SHUT_RDWR)
        except SocketError as e:
            code, message = e.args
            if code == 107:
                pass # KVS: not well understood, not tested. It seems some quick (local) servers close the connection before this point is reached. It may happen more generally. In any case, it is based on a truely existing phenomenon
            else:
                raise
        self._sok.close()
