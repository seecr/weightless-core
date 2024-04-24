## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2015, 2018-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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
from ssl import wrap_socket, SSL_ERROR_WANT_READ, SSL_ERROR_WANT_WRITE, SSLError, SSLContext, PROTOCOL_TLS_CLIENT, CERT_NONE
from sys import exc_info, getdefaultencoding

from weightless.core import compose, identify, Observable, autostart, Yield
from weightless.io import Suspend, TimeoutException
from weightless.http import REGEXP, HTTP, FORMAT, parseHeaders

CRLF = HTTP.CRLF


class HttpRequest1_1(Observable):
    """
    Uses minimal HTTP/1.1 implementation for Persistent Connections.
    """

    def httprequest1_1(self, host, port, request, body=None, headers=None, secure=False, prio=None, method='GET', timeout=None, bodyMaxSize=None):
        g = _do(method=method, host=host, port=port, request=request, headers=headers, body=body, bodyMaxSize=bodyMaxSize, secure=secure, prio=prio, observable=self)
        kw = {}
        if timeout is not None:
            def onTimeout():
                g.throw(TimeoutException().with_traceback(None))

            kw = {
                'timeout': timeout,
                'onTimeout': onTimeout,
            }

        s = Suspend(doNext=g.send, **kw)
        yield s
        result = s.getResult()
        return list(result)


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
                b'version': statusAndHeaders['HTTPVersion'],
                b'status': statusAndHeaders['StatusCode'],
                b'reason': statusAndHeaders['ReasonPhrase'],
            }) + b''.join(
                FORMAT.Header % (h, v)
                for h, v in
                sorted(statusAndHeaders['Headers'].items())
            )
        return _statusAndHeaders + CRLF + body


@identify
@compose
def _do(observable, method, host, port, request, body=None, headers=None, bodyMaxSize=None, secure=False, prio=None):
    method = method if type(method) is bytes else method.encode()
    request = request if type(request) is bytes else request.encode()
    _assertSupportedMethod(method)
    headers = headers or {}
    retryOnce = False
    this = yield # this generator, from @identify
    suspend = yield # suspend object, from Suspend.__call__

    try:
        ## Connect or re-use from pool.
        suspend._reactor.addProcess(process=this.__next__, prio=prio)
        try:
            yield Yield  # After this yield, Suspend._whenDone filled-in (by Suspend.__call__(reactor, whenDone)) and thus throwing is safe again.
            sok = yield observable.any.getPooledSocket(host=host, port=port)
        finally:
            suspend._reactor.removeProcess(process=this.__next__)

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
                    suspend._reactor.addWriter(sok, this.__next__, prio=prio)
                    try:
                        yield Yield
                        # error checking
                        if body:
                            data = body
                            if type(data) is str:
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
                    suspend._reactor.addReader(sok, this.__next__, prio=prio)
                    try:
                        statusAndHeaders, body, doClose = yield _readHeaderAndBody(sok, method, requestHeaders=headers, bodyMaxSize=bodyMaxSize)
                    finally:
                        suspend._reactor.removeReader(sok)
                except (AssertionError, KeyboardInterrupt, SystemExit):
                    raise
                except (IOError, ValueError, KeyError) as e:
                    # Expected errors:
                    # - IOError (and subclasses socket.error and it's subclasses - incl. SSLError)
                    # - ValueError raised when all kinds of expectations about behaviour or data fail.
                    # - KeyError:
                    #   * suspend._reactor.remove(Reader|Writer) after a "bad file descriptor" removal;
                    #     (reactor oddness).
                    shutAndCloseOnce(ignoreExceptions=True)
                    if (not retryOnce) or sok.recievedData:
                        raise

                    retryOnce = False
                    observable.do.log(message="[HttpRequest1_1] Error when reusing socket for %s:%d. Trying again. Error was: %s\n" % (host, port, str(e)))
                    continue

                break

            ## Either put socket in a pool or close when we must.
            if doClose:
                shutAndCloseOnce()
            else:
                suspend._reactor.addProcess(process=this.__next__, prio=prio)
                try:
                    yield observable.any.putSocketInPool(host=host, port=port, sock=sok.unwrap_recievedData())
                finally:
                    suspend._reactor.removeProcess(process=this.__next__)
            suspend.resume((statusAndHeaders, body))
        except BaseException:
            shutAndCloseOnce(ignoreExceptions=True)
            raise
    except (AssertionError, KeyboardInterrupt, SystemExit):
        raise
    except TimeoutException:
        #sok.close() # recycle iso close
        # print_exc()   # Enable for debugging timeouts.
        pass
    except Exception:
        suspend.throw(*exc_info())
    finally:
        pass
        #sok.close() # recycle iso close
    yield  # wait for GC


def _assertSupportedMethod(method):
    if method == b'CONNECT':
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
    except SocketError as xxx_todo_changeme:
        (errno, msg) = xxx_todo_changeme.args
        if errno != EINPROGRESS:
            sok.close() # utter failure so close
            raise
    except Exception:
        sok.close() # utter failure so close
        raise

    suspend._reactor.addWriter(sok, this.__next__, prio=prio)
    try:
        yield Yield
        suspend._reactor.removeWriter(sok)
        err = sok.getsockopt(SOL_SOCKET, SO_ERROR)
        if err != 0:    # connection created succesfully?
            sok.close() # utter failure so close
            raise IOError(err)
    finally:
        pass

    if secure:
        sok = yield _sslHandshake(sok, this, suspend, prio)
    sok = SocketWrapper(sok)
    return sok

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
    if 'host' not in [k.lower() for k in list(headers.keys())]:
        headers['Host'] = host
    data += b''.join(k.encode()+b': '+str(v).encode()+b'\r\n' for (k,v) in list(headers.items()))
    data += b'\r\n'
    yield _asyncSend(sok, data)

def _asyncSend(sok, data):
    while data != b"":
        size = sok.send(data)
        data = data[size:]
        yield Yield

def _readHeaderAndBody(sok, method, requestHeaders, bodyMaxSize):
    statusAndHeaders, rest = yield _readHeader(sok)
    readStrategy, doClose = _determineBodyReadStrategy(statusAndHeaders=statusAndHeaders, method=method, requestHeaders=requestHeaders, bodyMaxSize=bodyMaxSize)
    body = yield readStrategy(sok, rest)
    return [statusAndHeaders, body, doClose]

def _readHeader(sok, rest=b''):
    responses = rest
    rest = b''
    while True:
        response = yield _asyncRead(sok)
        if response is _CLOSED:
            raise ValueError('Premature close')
        responses += response

        match = REGEXP.RESPONSE.match(responses)
        if match:
            break

        # TODO: check some max. statusline + header size (or bail).

    if match.end() < len(responses):
        rest = responses[match.end():]

    statusAndHeaders = match.groupdict()
    headers = parseHeaders(statusAndHeaders['_headers'])
    del statusAndHeaders['_headers']
    statusAndHeaders['Headers'] = headers

    if statusAndHeaders['StatusCode'] == b'100':
        # 100 Continue response, eaten it - and then read the real response.
        statusAndHeaders, rest = yield _readHeader(sok, rest=rest)

    return [statusAndHeaders, rest]

def _determineBodyReadStrategy(statusAndHeaders, method, requestHeaders, bodyMaxSize=None):
    doClose = False
    if _determineDoCloseFromConnection(requestHeaders) or _determineDoCloseFromConnection(statusAndHeaders['Headers']) or (bodyMaxSize is not None):
        doClose = True
    statusCode = statusAndHeaders['StatusCode']
    contentLength = statusAndHeaders['Headers'].get(b'Content-Length')
    if contentLength:
        contentLength = int(contentLength.strip())

    transferEncoding = _parseTransferEncoding(statusAndHeaders['Headers'])

    ## HTTP/1.0
    if statusAndHeaders['HTTPVersion'] != b'1.1':
        doClose = True
        if _bodyDisallowed(method, statusCode):
            return _readAssertNoBody, doClose
        if contentLength is None:
            return _readCloseDelimitedBody(bodyMaxSize), doClose
        return partial(_readContentLengthDelimitedBody(bodyMaxSize), contentLength=contentLength), doClose

    ## HTTP/1.1
    if _bodyDisallowed(method, statusCode):
        return _readAssertNoBody, doClose

    if transferEncoding and transferEncoding[-1:] == [b'chunked']:
        return _readChunkedDelimitedBody(bodyMaxSize), doClose
    elif contentLength is not None:
        return partial(_readContentLengthDelimitedBody(bodyMaxSize), contentLength=contentLength), doClose

    doClose = True
    return _readCloseDelimitedBody(bodyMaxSize), doClose

def _bodyDisallowed(method, statusCode):
    # Status-codes also without body, but should never happen:
    #   - 1XX:
    #       * 100 (continue) already handled.
    #       * 101 (switching protocols) not supported - just don't send the "Upgrade" request header.
    if statusCode[0] == ord('1'):
        raise ValueError('1XX status code recieved.')
    return method == b'HEAD' or statusCode in [b'204', b'304']

def _readAssertNoBody(sok, rest):
    if rest:
        raise ValueError('Body not empty.')
    return b''
    yield

def _bodyMaxSize(fn):
    def _setMaxSize(bodyMaxSize):
        def _maxSized(*a, **kw):
            g = compose(fn(*a, **kw))
            responses = b''
            try:
                while True:
                    v = g.__next__()
                    if v is Yield or callable(v):
                        yield v
                        continue

                    responses += v

                    if (bodyMaxSize is not None) and len(responses) >= bodyMaxSize:
                        g.close()
                        return responses[:bodyMaxSize]
            except StopIteration:
                return responses if (bodyMaxSize is None) else responses[:bodyMaxSize]

        return _maxSized

    return _setMaxSize

@_bodyMaxSize
def _readCloseDelimitedBody(sok, rest):
    response = rest  # Must be empty-string at least
    if response is _CLOSED:
        return
    elif response:
        yield response

    while True:
        response = yield _asyncRead(sok)
        if response is _CLOSED:
            break

        yield response

@_bodyMaxSize
def _readContentLengthDelimitedBody(sok, rest, contentLength):
    response = rest  # Must be empty-string at least
    bytesToRead = contentLength - len(rest)
    if bytesToRead < 0:
        raise ValueError('Excess bytes (> Content-Length) read.')

    if response:
        yield response

    while bytesToRead:
        response = yield _asyncRead(sok)
        if response is _CLOSED:
            raise ValueError('Premature close')
        bytesToRead -= len(response)
        if bytesToRead < 0:
            raise ValueError('Excess bytes (> Content-Length) read.')
        yield response

@_bodyMaxSize
def _readChunkedDelimitedBody(sok, rest):
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
                yield resp
                message = None

            resp = g.send(message)
    except StopIteration:
        pass

def _sslHandshake(sok, this, suspend, prio):
    ssl_context = SSLContext(PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname=False
    ssl_context.verify_mode = CERT_NONE
    sok = ssl_context.wrap_socket(sok, do_handshake_on_connect=False)

    count = 0
    while count < 254:
        count += 1
        try:
            sok.do_handshake()
            sok.setsockopt(SOL_TCP, TCP_QUICKACK, 1)  # May be read or write; set just in case it's read.
            break
        except SSLError as err:
            if err.args[0] == SSL_ERROR_WANT_READ:
                suspend._reactor.addReader(sok, this.__next__, prio=prio)
                yield Yield
                suspend._reactor.removeReader(sok)
            elif err.args[0] == SSL_ERROR_WANT_WRITE:
                suspend._reactor.addWriter(sok, this.__next__, prio=prio)
                yield Yield
                suspend._reactor.removeWriter(sok)
            else:
                raise
    if count == 254:
        raise ValueError("SSL handshake failed.")
    return sok

def _requestLine(method, request):
    assert type(method) is bytes
    assert type(request) is bytes
    if request == b'':
        request = b'/'
    return b"%b %b HTTP/1.1\r\n" % (method, request)

def _determineDoCloseFromConnection(headers):
    connectionHeaderValue = headers.get('Connection')
    if connectionHeaderValue:
        connection = [v.strip() for v in connectionHeaderValue.lower().strip().split(',')]
        if 'close' in connection:
            return True

    return False

def _parseTransferEncoding(responseHeaders):
    transferEncoding = responseHeaders.get(b'Transfer-Encoding')
    if transferEncoding:
        # transfer-extension's should be parsed differently (see: https://tools.ietf.org/html/rfc7230#section-4 ) - but not important here.
        transferEncoding = [v.strip() for v in transferEncoding.lower().strip().split(b',')]
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
    data = b''
    while True:
        _in = yield
        data += _in
        match = _TRAILERS_RE.match(data)
        if match:
            break

    trailersStr = match.groupdict()['_trailers']  # Unparsed trailers or None
    end = match.end()
    rest = data[end:]
    return [trailersStr, rest]

def _oneChunk():
    data = b''
    while True:
        _in = yield
        data += _in
        match = _CHUNK_RE.match(data)
        if match:
            break

    size = int(match.group(1), 16)
    data = data[match.end():]

    if size == 0:
        return None, data

    while (len(data) - _CRLF_LEN) < size:
        _in = yield
        data += _in

    chunk = data[:size]
    data = data[(size + _CRLF_LEN):]
    return chunk, data

def _asyncRead(sok):
    while True:
        yield Yield
        try:
            response = sok.recv(4096)  # bufsize *must* be large enough - SSL Socket recv will hang indefinitely otherwise (until a timeout if given).
            sok.setsockopt(SOL_TCP, TCP_QUICKACK, 1)
        except SSLError as e:
            if e.errno != SSL_ERROR_WANT_READ:
                raise
            sok.setsockopt(SOL_TCP, TCP_QUICKACK, 1)
            continue
        if response == b'':
            return _CLOSED
        return response

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


_ALLOWED_OPTIONAL_ADAPTER_ARGUMENTS = set(['body', 'headers', 'method', 'prio', 'ssl', 'timeout', 'bodyMaxSize'])
_noop = lambda *a, **kw: None
_CRLF_LEN = len(CRLF)
_CHUNK_RE = re.compile(r'([0-9a-fA-F]+)(?:;[^\r\n]+|)\r\n'.encode())  # Ignores chunk-extensions
_TRAILERS_RE = re.compile(b"(?:(?P<_trailers>(?:" + HTTP.message_header + b')+)' + CRLF + b'|' + CRLF + b')')
_CLOSED = type('CLOSED', (object,), {})()
