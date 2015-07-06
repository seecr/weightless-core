## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2015 Seecr (Seek You Too B.V.) http://seecr.nl
# Copyright (C) 2015 Koninklijke Bibliotheek (KB) http://www.kb.nl
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

import re
from errno import EINPROGRESS
from functools import partial
from socket import socket, error as SocketError, SOL_SOCKET, SO_ERROR, SHUT_RDWR, SOL_TCP, TCP_KEEPINTVL, TCP_KEEPIDLE, TCP_KEEPCNT, SO_KEEPALIVE, TCP_QUICKACK, TCP_NODELAY
from ssl import wrap_socket, SSL_ERROR_WANT_READ, SSL_ERROR_WANT_WRITE, SSLError
from sys import exc_info, getdefaultencoding

from weightless.core import compose, identify, Observable, autostart
from weightless.io import Suspend, TimeoutException
from weightless.http import REGEXP, HTTP, FORMAT, parseHeaders

CRLF = HTTP.CRLF


class HttpRequest1_1(Observable):
    """
    Uses minimal HTTP/1.1 implementation for Persistent Connections.
    """

    def httprequest1_1(self, host, port, request, body=None, headers=None, secure=False, prio=None, method='GET', timeout=None):
        g = _do(method=method, host=host, port=port, request=request, headers=headers, body=body, secure=secure, prio=prio, observable=self)
        kw = {}
        if timeout is not None:
            def onTimeout():
                g.throw(TimeoutException, TimeoutException(), None)

            kw = {
                'timeout': timeout,
                'onTimeout': onTimeout,
            }

        s = Suspend(doNext=g.send, **kw)
        yield s
        result = s.getResult()
        raise StopIteration(result)


class HttpRequestAdapter(Observable):
    def httprequest(self, host, port, request, **kwargs):
        kwargKeys = set(kwargs.keys())
        if ('proxyServer' in kwargKeys) or ('handlePartialResponse' in kwargKeys):
            raise TypeError('proxyServer and handlePartialResponse arguments not supported in HttpRequest1_1 - so cannot adapt.')
        if not kwargKeys.issubset(_ALLOWED_OPTIONAL_ADAPTER_ARGUMENTS):
            raise TypeError('Unexpected argument(s): ' + ', '.join(kwargKeys.difference(_ALLOWED_OPTIONAL_ADAPTER_ARGUMENTS)))

        translated = {}
        if 'ssl' in kwargKeys:
            translated['secure'] = kwargs.pop('ssl')

        adapteeKwargs = dict(kwargs, **translated)

        statusAndHeaders, body = yield self.any.httprequest1_1(host=host, port=port, request=request, **adapteeKwargs)
        _statusAndHeaders = (FORMAT.StatusLine % {
                'version': statusAndHeaders['HTTPVersion'],
                'status': statusAndHeaders['StatusCode'],
                'reason': statusAndHeaders['ReasonPhrase'],
            }) + ''.join(
                FORMAT.Header % (h, v)
                for h, v in
                sorted(statusAndHeaders['Headers'].items())
            )
        raise StopIteration(_statusAndHeaders + CRLF + body)


@identify
@compose
def _do(observable, method, host, port, request, body=None, headers=None, secure=False, prio=None):
    _assertSupportedMethod(method)
    headers = headers or {}
    retryOnce = False
    this = yield # this generator, from @identify
    suspend = yield # suspend object, from Suspend.__call__

    try:
        ## Connect or re-use from pool.
        suspend._reactor.addProcess(process=this.next, prio=prio)
        try:
            yield  # After this yield, Suspend._whenDone filled-in (by Suspend.__call__(reactor, whenDone)) and thus throwing is safe again.
            sok = yield observable.any.getPooledSocket(host=host, port=port)
        finally:
            suspend._reactor.removeProcess(process=this.next)

        if sok:
            sok = SocketWrapper(sok)
            retryOnce = True

        try:
            while True:  # do ... while (retryOnce) "loop"
                if not retryOnce:
                    shutAndCloseOnce = _noop
                    sok = yield _createSocket(host, port, secure, this, suspend, prio)
                shutAndCloseOnce = _shutAndCloseOnce(sok)

                try:
                    ## Send Request-Line and Headers.
                    suspend._reactor.addWriter(sok, this.next, prio=prio)
                    try:
                        yield
                        # error checking
                        if body:
                            data = body
                            if type(data) is unicode:
                                data = data.encode(getdefaultencoding())
                            # Only specify Content-Length when there is a body, because:
                            #   - Having Content-Length or Transfer-Encoding specified on request, detemines wether a body exists;
                            #     see: https://tools.ietf.org/html/rfc7230#section-3.3 (paragraphs 2 & 3).
                            #   - Cannot handle Content-Length or Transfer-Encoding set in headers!
                            headers.update({'Content-Length': len(data)})
                        yield _sendHttpHeaders(sok, method, request, headers, host)
                        if body:
                            yield _asyncSend(sok, data)
                    finally:
                        suspend._reactor.removeWriter(sok)

                    ## Read response (& handle 100 Continue #fail)
                    suspend._reactor.addReader(sok, this.next, prio=prio)
                    try:
                        statusAndHeaders, body, doClose = yield _readHeaderAndBody(sok, method, requestHeaders=headers)
                    finally:
                        suspend._reactor.removeReader(sok)
                except (AssertionError, KeyboardInterrupt, SystemExit):
                    raise
                except (IOError, ValueError, KeyError), e:
                    # Expected errors:
                    # - IOError (and subclasses socket.error and it's subclasses - incl. SSLError)
                    # - ValueError raised when all kinds of expectations about behaviour or data fail.
                    # - KeyError:
                    #   * suspend._reactor.remove(Reader|Writer) after a "bad file descriptor" removal;
                    #     (reactor oddness).
                    if (not retryOnce) or sok.recievedData:
                        raise

                    retryOnce = False
                    observable.do.log(message="[HttpRequest1_1] Error when reusing socket for %s:%d. Trying again. Error was: %s\n" % (host, port, str(e)))
                    shutAndCloseOnce(ignoreExceptions=True)
                    continue

                break

            ## Either put socket in a pool or close when we must.
            if doClose:
                shutAndCloseOnce()
            else:
                suspend._reactor.addProcess(process=this.next, prio=prio)
                try:
                    yield observable.any.putSocketInPool(host=host, port=port, sock=sok.unwrap_recievedData())
                finally:
                    suspend._reactor.removeProcess(process=this.next)
            suspend.resume((statusAndHeaders, body))
        except BaseException:
            shutAndCloseOnce(ignoreExceptions=True)
            raise
    except (AssertionError, KeyboardInterrupt, SystemExit):
        raise
    except TimeoutException:
        pass
    except Exception:
        suspend.throw(*exc_info())
    yield  # wait for GC


def _assertSupportedMethod(method):
    if method == 'CONNECT':
        raise ValueError('CONNECT method unsupported.')

def _createSocket(host, port, secure, this, suspend, prio):
    # No "yield", so add*/remove* not needed.
    sok = socket()
    sok.setblocking(0)
    sok.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)
    sok.setsockopt(SOL_TCP, TCP_KEEPIDLE, 60*10)
    sok.setsockopt(SOL_TCP, TCP_KEEPINTVL, 75)
    sok.setsockopt(SOL_TCP, TCP_KEEPCNT, 9)
    sok.setsockopt(SOL_TCP, TCP_NODELAY, 1)
    try:
        sok.connect((host, port))
    except SocketError, (errno, msg):
        if errno != EINPROGRESS:
            raise

    suspend._reactor.addWriter(sok, this.next, prio=prio)
    try:
        yield
        err = sok.getsockopt(SOL_SOCKET, SO_ERROR)
        if err != 0:    # connection created succesfully?
            raise IOError(err)
    finally:
        suspend._reactor.removeWriter(sok)

    if secure:
        sok = yield _sslHandshake(sok, this, suspend, prio)
    sok = SocketWrapper(sok)
    raise StopIteration(sok)

def _shutAndCloseOnce(sok):
    state = []
    def shutAndCloseOnce(ignoreExceptions=False):
        if 's' not in state:
            state.append('s')
            if ignoreExceptions:
                try:
                    sok.shutdown(SHUT_RDWR)
                except (AssertionError, KeyboardInterrupt, SystemExit):
                    raise
                except Exception:
                    pass
            else:
                sok.shutdown(SHUT_RDWR)
        if 'c' not in state:
            state.append('c')
            sok.close()
    return shutAndCloseOnce

def _sendHttpHeaders(sok, method, request, headers, host):
    data = _requestLine(method, request)
    if 'host' not in [k.lower() for k in headers.keys()]:
        headers['Host'] = host
    data += ''.join('%s: %s\r\n' % i for i in headers.items())
    data += '\r\n'
    yield _asyncSend(sok, data)

def _asyncSend(sok, data):
    while data != "":
        size = sok.send(data)
        data = data[size:]
        yield

def _readHeaderAndBody(sok, method, requestHeaders):
    statusAndHeaders, rest = yield _readHeader(sok)
    readStrategy, doClose = _determineBodyReadStrategy(statusAndHeaders=statusAndHeaders, method=method, requestHeaders=requestHeaders)
    body = yield readStrategy(sok, rest)
    raise StopIteration((statusAndHeaders, body, doClose))

def _readHeader(sok, rest=''):
    responses = rest
    rest = ''
    while True:
        response = yield _asyncRead(sok)
        if response is _CLOSED:
            raise ValueError('Premature close')
        responses += response

        match = REGEXP.RESPONSE.match(responses)
        if match:
            # TODO: check some max. statusline + header size (or bail).
            break

    if match.end() < len(responses):
        rest = responses[match.end():]

    statusAndHeaders = match.groupdict()
    headers = parseHeaders(statusAndHeaders['_headers'])
    del statusAndHeaders['_headers']
    statusAndHeaders['Headers'] = headers

    if statusAndHeaders['StatusCode'] == '100':
        # 100 Continue response, eaten it - and then read the real response.
        statusAndHeaders, rest = yield _readHeader(sok, rest=rest)

    raise StopIteration((statusAndHeaders, rest))

def _determineBodyReadStrategy(statusAndHeaders, method, requestHeaders):
    doClose = False
    if _determineDoCloseFromConnection(requestHeaders) or _determineDoCloseFromConnection(statusAndHeaders['Headers']):
        doClose = True
    statusCode = statusAndHeaders['StatusCode']
    contentLength = statusAndHeaders['Headers'].get('Content-Length')
    if contentLength:
        contentLength = int(contentLength.strip())
    transferEncoding = _parseTransferEncoding(statusAndHeaders['Headers'])

    ## HTTP/1.0
    if statusAndHeaders['HTTPVersion'] != '1.1':
        doClose = True
        if _bodyDisallowed(method, statusCode):
            return _readAssertNoBody, doClose
        if contentLength is None:
            return _readCloseDelimitedBody, doClose
        return partial(_readContentLengthDelimitedBody, contentLength=contentLength), doClose

    ## HTTP/1.1
    if _bodyDisallowed(method, statusCode):
        return _readAssertNoBody, doClose

    if transferEncoding and transferEncoding[-1:] == ['chunked']:
        return _readChunkedDelimitedBody, doClose
    elif contentLength is not None:
        return partial(_readContentLengthDelimitedBody, contentLength=contentLength), doClose

    doClose = True
    return _readCloseDelimitedBody, doClose

def _bodyDisallowed(method, statusCode):
    # Status-codes also without body, but should never happen:
    #   - 1XX:
    #       * 100 (continue) already handled.
    #       * 101 (switching protocols) not supported - just don't send the "Upgrade" request header.
    if statusCode.startswith('1'):
        raise ValueError('1XX status code recieved.')
    return method == 'HEAD' or statusCode in ['204', '304']

def _readAssertNoBody(sok, rest):
    if rest:
        raise ValueError('Body not empty.')
    raise StopIteration('')
    yield

def _readCloseDelimitedBody(sok, rest):
    responses = rest  # Must be empty-string at least
    while True:
        response = yield _asyncRead(sok)
        if response is _CLOSED:
            break
        responses += response
    raise StopIteration(responses)

def _readContentLengthDelimitedBody(sok, rest, contentLength):
    responses = rest  # Must be empty-string at least
    bytesToRead = contentLength - len(rest)
    if bytesToRead < 0:
        raise ValueError('Excess bytes (> Content-Length) read.')

    while bytesToRead:
        response = yield _asyncRead(sok)
        if response is _CLOSED:
            raise ValueError('Premature close')
        responses += response
        bytesToRead -= len(response)
        if bytesToRead < 0:
            raise ValueError('Excess bytes (> Content-Length) read.')
    raise StopIteration(responses)

def _readChunkedDelimitedBody(sok, rest):
    responses = ''
    g = _deChunk()
    try:
        if rest:
            resp = g.send(rest)
        else:
            resp = None

        while True:
            if resp is None:
                message = yield _asyncRead(sok)
                if message is _CLOSED:
                    g.close()
                    raise ValueError('Premature close')
            else:
                responses += resp
                message = None

            resp = g.send(message)
    except StopIteration:
        pass

    raise StopIteration(responses)

def _sslHandshake(sok, this, suspend, prio):
    sok = wrap_socket(sok, do_handshake_on_connect=False)
    count = 0
    while count < 254:
        count += 1
        try:
            sok.do_handshake()
            sok.setsockopt(SOL_TCP, TCP_QUICKACK, 1)  # May be read or write; set just in case it's read.
            break
        except SSLError as err:
            if err.args[0] == SSL_ERROR_WANT_READ:
                suspend._reactor.addReader(sok, this.next, prio=prio)
                yield
                suspend._reactor.removeReader(sok)
            elif err.args[0] == SSL_ERROR_WANT_WRITE:
                suspend._reactor.addWriter(sok, this.next, prio=prio)
                yield
                suspend._reactor.removeWriter(sok)
            else:
                raise
    if count == 254:
        raise ValueError("SSL handshake failed.")
    raise StopIteration(sok)

def _requestLine(method, request):
    return "%s %s HTTP/1.1\r\n" % (method, request)

def _determineDoCloseFromConnection(headers):
    connectionHeaderValue = headers.get('Connection')
    if connectionHeaderValue:
        connection = [v.strip() for v in connectionHeaderValue.lower().strip().split(',')]
        if 'close' in connection:
            return True

    return False

def _parseTransferEncoding(responseHeaders):
    transferEncoding = responseHeaders.get('Transfer-Encoding')
    if transferEncoding:
        # transfer-extension's should be parsed differently (see: https://tools.ietf.org/html/rfc7230#section-4 ) - but not important here.
        transferEncoding = [v.strip() for v in transferEncoding.lower().strip().split(',')]
        return transferEncoding

@autostart
@compose
def _deChunk():
    while True:
        chunk = yield _oneChunk()
        if not chunk:
            break

        yield chunk

    trailersStr, rest = yield _trailers()

    if rest:
        raise ValueError('Data after last chunk')

def _trailers():
    data = ''
    while True:
        _in = yield
        data += _in
        match = _TRAILERS_RE.match(data)
        if match:
            break

    trailersStr = match.groupdict()['_trailers']  # Unparsed trailers or None
    end = match.end()
    rest = data[end:]
    raise StopIteration((trailersStr, rest))

def _oneChunk():
    data = ''
    while True:
        _in = yield
        data += _in
        match = _CHUNK_RE.match(data)
        if match:
            break

    size = int(match.group(1), 16)
    data = data[match.end():]

    if size == 0:
        pushback = (data,) if data else ()
        raise StopIteration(None, *pushback)

    while (len(data) - _CRLF_LEN) < size:
        _in = yield
        data += _in

    chunk = data[:size]
    data = data[(size + _CRLF_LEN):]
    pushback = (data,) if data else ()
    raise StopIteration(chunk, *pushback)

def _asyncRead(sok):
    while True:
        yield
        try:
            response = sok.recv(4096) # error checking
            sok.setsockopt(SOL_TCP, TCP_QUICKACK, 1)
        except SSLError, e:
            if e.errno != SSL_ERROR_WANT_READ:
                raise
            sok.setsockopt(SOL_TCP, TCP_QUICKACK, 1)
            continue

        if response == '':
            raise StopIteration(_CLOSED)
        raise StopIteration(response)

class SocketWrapper(object):
    def __init__(self, sok):
        self.recievedData = False
        self.__sok_wrapped__ = sok

    def recv(self, *args, **kwargs):
        data = self.__sok_wrapped__.recv(*args, **kwargs)
        if data:
            self.recievedData = True
            self.recv = self.__sok_wrapped__.recv  # Unwrap this method.
        return data

    def unwrap_recievedData(self):
        return self.__sok_wrapped__

    def __getattr__(self, attr):
        value = getattr(self.__sok_wrapped__, attr)
        setattr(self, attr, value)  # Only methods and read-only properties exist on a socket-obj.
        return value


_ALLOWED_OPTIONAL_ADAPTER_ARGUMENTS = set(['body', 'headers', 'method', 'prio', 'ssl', 'timeout'])
_noop = lambda *a, **kw: None
_CRLF_LEN = len(CRLF)
_CHUNK_RE = re.compile(r'([0-9a-fA-F]+)(?:;[^\r\n]+|)\r\n')  # Ignores chunk-extensions
_TRAILERS_RE = re.compile("(?:(?P<_trailers>(?:" + HTTP.message_header + ')+)' + CRLF + '|' + CRLF + ')')
_CLOSED = type('CLOSED', (object,), {})()
