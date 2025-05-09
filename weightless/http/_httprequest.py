## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2016, 2020-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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

from sys import exc_info, getdefaultencoding
from socket import socket, error as SocketError, SOL_SOCKET, SO_ERROR, SHUT_RDWR, SOL_TCP, TCP_KEEPINTVL, TCP_KEEPIDLE, TCP_KEEPCNT, SO_KEEPALIVE
from errno import EINPROGRESS
from ssl import SSL_ERROR_WANT_READ, SSL_ERROR_WANT_WRITE, SSLError, SSLContext, PROTOCOL_TLS_CLIENT, CERT_NONE

from functools import partial

from weightless.io import Suspend, TimeoutException, TooBigResponseException
from weightless.core import compose, identify
from urllib.parse import urlsplit


def httprequest(host, port, request, body=None, headers=None, proxyServer=None, ssl=False, prio=None, handlePartialResponse=None, method='GET', timeout=None, maxResponseSize=None):
    g = _do(method, host=host, port=port, request=request, headers=headers, proxyServer=proxyServer, body=body, ssl=ssl, prio=prio, handlePartialResponse=handlePartialResponse, maxResponseSize=maxResponseSize)
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
    return result

httpget = httprequest
httppost = partial(httprequest, method='POST')
httpdelete = partial(httprequest, method='DELETE')
httpput = partial(httprequest, method='PUT')

httpsget = partial(httpget, ssl=True)
httpspost = partial(httppost, ssl=True)
httpsdelete = partial(httpdelete, ssl=True)
httpsput = partial(httpput, ssl=True)

class HttpRequest(object):
    @staticmethod
    def httprequest(**kwargs):
        result = yield httprequest(**kwargs)
        return result

def _createSocket():
    sok = socket()
    sok.setblocking(0)
    sok.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)
    sok.setsockopt(SOL_TCP, TCP_KEEPIDLE, 60*10)
    sok.setsockopt(SOL_TCP, TCP_KEEPINTVL, 75)
    sok.setsockopt(SOL_TCP, TCP_KEEPCNT, 9)
    return sok

@identify
@compose
def _do(method, host, port, request, body=None, headers=None, proxyServer=None, ssl=False, prio=None, handlePartialResponse=None, maxResponseSize=None):
    headers = headers or {}
    this = yield # this generator, from @identify
    suspend = yield # suspend object, from Suspend.__call__

    sok = _createSocket()
    if proxyServer:
        proxy = urlsplit(proxyServer)
        origHost = host
        origPort = port
        host = proxy.hostname
        port = proxy.port or 80

    try:
        sok.connect((host, port))
    except SocketError as e:
        (errno, msg) = e.args
        if errno != EINPROGRESS:
            sok.close() # deze moet echt
            raise
    except Exception:
        sok.close() # deze moet echt
        raise

    try:
        suspend._reactor.addWriter(sok, this.__next__, prio=prio)
        try:
            yield
            err = sok.getsockopt(SOL_SOCKET, SO_ERROR)
            if err != 0:    # connection created succesfully?
                raise IOError(err)
        finally:
            suspend._reactor.removeWriter(sok)

        if proxyServer:
            # hotfix EG d.d. 1/3/14
            sok.sendall("CONNECT {host} HTTP/1.0\r\nHost: {host}\r\n\r\n".format(
                    host='{}:{}'.format(origHost, origPort)).encode())
            suspend._reactor.addReader(sok, this.__next__, prio=prio)
            try:
                # hotfix EG d.d. 1/3/14
                response = b''
                while True:
                    yield
                    fragment = sok.recv(4096)
                    if fragment == b'':
                        break
                    response += fragment
                    if b"\r\n\r\n" in response:
                        break
                status = response.split()[:2]
                if not b"200" in status:
                    raise ValueError("Failed to connect through proxy")
                # end hotfix
            finally:
                suspend._reactor.removeReader(sok)

        if ssl:
            sok = yield _sslHandshake(sok, this, suspend, prio)

        suspend._reactor.addWriter(sok, this.__next__, prio=prio)
        yield
        try:
            # error checking
            if body:
                data = body
                if type(data) is str:
                    data = data.encode(getdefaultencoding())
                headers.update({'Content-Length': len(data)})
            yield _sendHttpHeaders(sok, method, request, headers)
            if body:
                yield _asyncSend(sok, data)
        finally:
            suspend._reactor.removeWriter(sok)
        suspend._reactor.addReader(sok, this.__next__, prio=prio)
        responses = []
        size = 0
        try:
            while True:
                yield
                try:
                    response = sok.recv(4096) # error checking
                except SSLError as e:
                    if e.errno != SSL_ERROR_WANT_READ:
                        raise
                    continue
                if response == b'':
                    break
                size += len(response)
                if not maxResponseSize is None and size > maxResponseSize:
                    raise TooBigResponseException(maxResponseSize)

                if handlePartialResponse:
                    handlePartialResponse(response)
                else:
                    responses.append(response)
        finally:
            suspend._reactor.removeReader(sok)
            try:
                sok.shutdown(SHUT_RDWR)
            except OSError as e:
                if e.errno != 107:
                    raise
            sok.close()
        suspend.resume(None if handlePartialResponse else b''.join(responses))
    except (AssertionError, KeyboardInterrupt, SystemExit):
        raise
    except TimeoutException:
        sok.close()
    except Exception:
        suspend.throw(*exc_info())
    finally:
        sok.close() # deze lijkt echt nodig te zijn
    yield

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
            break
        except SSLError as err:
            if err.args[0] == SSL_ERROR_WANT_READ:
                suspend._reactor.addReader(sok, this.__next__, prio=prio)
                yield
                suspend._reactor.removeReader(sok)
            elif err.args[0] == SSL_ERROR_WANT_WRITE:
                suspend._reactor.addWriter(sok, this.__next__, prio=prio)
                yield
                suspend._reactor.removeWriter(sok)
            else:
                raise
    if count == 254:
        raise ValueError("SSL handshake failed.")
    return sok

def _asyncSend(sok, data):
    data = data if type(data) is bytes else data.encode()
    while data != b"":
        size = sok.send(data)
        data = data[size:]
        yield

def _sendHttpHeaders(sok, method, request, headers):
    data = _requestLine(method, request)
    if headers:
        data += ''.join('%s: %s\r\n' % i for i in list(headers.items()))
    data += '\r\n'
    yield _asyncSend(sok, data)

def _requestLine(method, request):
    if request == '':
        request = '/'
    return "%s %s HTTP/1.0\r\n" % (method, request)
