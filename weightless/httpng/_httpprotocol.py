## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2019 Seecr (Seek You Too B.V.) http://seecr.nl
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


from cgi import parse_qs, parse_header
from urllib.parse import urlsplit

from weightless.core import Observable
from weightless.core.utils import readRe, copyBytes
from weightless.io import Timer, TimeoutException
from weightless.http import HTTP, FORMAT, REGEXP

MAXREQUESTSIZE = 10*1024 # max size of RequestLine (including URI) and Headers
REQUESTTIMEOUT = 1

class HeaderDict(dict):
    def __missing__(self, key):
        return {}

def splitNameAndValue(nameAndValue):
    name, value = nameAndValue.split(':',1)
    return name.strip().lower(), value.strip()

def parseHeaders(kwargs):
    headers = HeaderDict(
        (name, {value: parms})
            for ((name, value), parms) in ((splitNameAndValue(nameAndValue), parms)
                for nameAndValue, parms in (parse_header(headerline)
                    for headerline in kwargs['_headers'].split(HTTP.CRLF)[:-1]
                )
            ))
    kwargs['Headers'] = headers
    del kwargs['_headers']
    return headers

class HttpProtocol(Observable):

    Timer = Timer

    def processConnection(self):
        while True:
            try:
                with HttpProtocol.Timer(REQUESTTIMEOUT):
                    reqArgs = yield readRe(REGEXP.REQUEST, MAXREQUESTSIZE)
            except OverflowError:
                yield requestEntityTooLarge()
                yield HTTP.CRLF
                return
            except TimeoutException as e:
                yield requestTimeout()
                yield HTTP.CRLF
                return
            #except Exception:
            #    yield badRequest()
            #    yield HTTP.CRLF
            #    return
            headers = parseHeaders(reqArgs)
            scheme, netloc, path, query, fragment = urlsplit(reqArgs['RequestURI'])
            netloc = tuple(netloc.split(':'))
            query = parse_qs(query)
            if 'content-length' in headers:
                length = int(list(headers['content-length'].keys())[0])
                reqArgs['ContentLength'] = length
            chunked = 'transfer-encoding' in headers and list(headers['transfer-encoding'].keys())[0] == 'chunked'
            try:
                handler = self.any.processRequest(
                    scheme=scheme, netloc=netloc, path=path, query=query, fragment=fragment, **reqArgs)
            except AttributeError:
                if 'expect' in headers:
                    yield expectationFailed()
                else:
                    yield notImplemented()
            else:
                if 'expect' in headers:
                    yield hundredContinue()
                if chunked:
                    handler = feedChunks(handler)
                yield handler
            if 'close' in headers['connection'] or reqArgs['HTTPVersion'] == '1.0':
                break


def feedChunks(handler):
    next(handler)
    while True:
        chunkSizeLine = yield readRe(REGEXP.CHUNK_SIZE_LINE, MAXREQUESTSIZE)
        size = int(chunkSizeLine['ChunkSize'], 16)
        if size == 0:
            yield handler.throw(StopIteration())
            break
        yield copyBytes(size, handler)
        yield readRe(REGEXP.CRLF, 2)
    for partialResponse in handler:
        yield partialResponse

def ok():
    version = 1.1
    status = 200
    reason = 'Ok'
    return FORMAT.StatusLine % locals()

def badRequest():
    version = 1.1
    status = 400
    reason = "Bad Request"
    return FORMAT.StatusLine % locals()

def notImplemented():
    version = 1.1
    status = 501
    reason = 'Not Implemented'
    return FORMAT.StatusLine % locals()

def requestEntityTooLarge():
    version = 1.1
    status = 413
    reason = 'Request Entity Too Large'
    return FORMAT.StatusLine % locals()

def requestTimeout():
    version = 1.1
    status = 408
    reason = 'Request Timeout'
    return FORMAT.StatusLine % locals()

def hundredContinue():
    version = 1.1
    status = 100
    reason = 'Continue'
    return FORMAT.StatusLine % locals()

def expectationFailed():
    version = 1.1
    status = 417
    reason = 'Expectation failed'
    return FORMAT.StatusLine % locals()

def headers(key, value):
    return FORMAT.Header % (key, value) + HTTP.CRLF

def noheaders():
    return HTTP.CRLF
