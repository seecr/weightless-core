## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2015 Seecr (Seek You Too B.V.) http://seecr.nl
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
from ssl import wrap_socket, SSL_ERROR_WANT_READ, SSL_ERROR_WANT_WRITE, SSLError
from functools import partial

from weightless.io import Suspend, TimeoutException
from weightless.core import compose, identify
from urlparse import urlsplit


# TODO:
# - extract socketPool
# - should retry failed requests on pooled sockets


def httprequest(host, port, request, body=None, headers=None, ssl=False, prio=None, handlePartialResponse=None, method='GET', timeout=None):
    g = _do(method, host=host, port=port, request=request, headers=headers, body=body, ssl=ssl, prio=prio, handlePartialResponse=handlePartialResponse)
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

# FIXME: meh...
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
        raise StopIteration(result)


@identify
@compose
def _do(method, host, port, request, body=None, headers=None, ssl=False, prio=None, handlePartialResponse=None):
    headers = headers or {}
    pool = POOL_REFACTOR_ME
    this = yield # this generator, from @identify
    suspend = yield # suspend object, from Suspend.__call__

    try:
        fromPool, sok = yield _getOrCreateSocket(host, port, ssl, pool, this, suspend, prio)

        suspend._reactor.addWriter(sok, this.next, prio=prio)
        yield
        try:
            # error checking
            if body:
                data = body
                if type(data) is unicode:
                    data = data.encode(getdefaultencoding())
                headers.update({'Content-Length': len(data)})
            yield _sendHttpHeaders(sok, method, request, headers)
            if body:
                yield _asyncSend(sok, data)
        finally:
            suspend._reactor.removeWriter(sok)
        suspend._reactor.addReader(sok, this.next, prio=prio)
        responses = []
        try:
            while True:
                yield
                try:
                    response = sok.recv(4096) # error checking
                except SSLError as e:
                    if e.errno != SSL_ERROR_WANT_READ:
                        raise
                    continue
                if response == '':
                    break

                if handlePartialResponse:
                    handlePartialResponse(response)
                else:
                    responses.append(response)
        finally:
            suspend._reactor.removeReader(sok)
        sok.shutdown(SHUT_RDWR)
        sok.close()
        suspend.resume(None if handlePartialResponse else ''.join(responses))
    except (AssertionError, KeyboardInterrupt, SystemExit):
        raise
    except TimeoutException:
        pass
    except Exception:
        suspend.throw(*exc_info())
    # Uber finally: sok.close() from line 108
    yield


def _getOrCreateSocket(host, port, ssl, pool, this, suspend, prio):
    suspend._reactor.addProcess(process=this.next, prio=prio)
    yield  # First "yield <data>" since start-of-composed & (this/g).send(<SuspendObj>).  After this yield, Suspend._whenDone filled-in and thus throwing is safe again.
    try:
        sok = pool.get(host, port)
        if sok:
            raise StopIteration((True, sok))  # fromPool, <sok>

        sok = _createSocket()
        try:
            sok.connect((host, port))
        except SocketError, (errno, msg):
            if errno != EINPROGRESS:
                raise
    finally:
        suspend._reactor.removeProcess(process=this.next)

    suspend._reactor.addWriter(sok, this.next, prio=prio)
    try:
        yield
        err = sok.getsockopt(SOL_SOCKET, SO_ERROR)
        if err != 0:    # connection created succesfully?
            raise IOError(err)
    finally:
        suspend._reactor.removeWriter(sok)

    if ssl:
        sok = yield _sslHandshake(sok, this, suspend, prio)
    raise StopIteration((False, sok))  # fromPool, <sok>


class SocketPool(object):
    # TODO:
    # - maximum size ("per destination" and "total in pool")
    # - maximum age
    # - periodically check for remotely killed sockets?

    def __init__(self):
        self._pool = {}

    def get(self, host, port):
        key = (host, port)
        socks = self._pool.get(key)
        if socks is None:
            return None

        try:
            return socks.pop(0)
        except IndexError:
            del self._pool[key]
            return None

    def put(self, host, port, sock):
        key = (host, port)
        self._pool.setdefault(key, []).append(sock)


def _createSocket():
    sok = socket()
    sok.setblocking(0)
    sok.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)
    sok.setsockopt(SOL_TCP, TCP_KEEPIDLE, 60*10)
    sok.setsockopt(SOL_TCP, TCP_KEEPINTVL, 75)
    sok.setsockopt(SOL_TCP, TCP_KEEPCNT, 9)
    return sok

def _sslHandshake(sok, this, suspend, prio):
    sok = wrap_socket(sok, do_handshake_on_connect=False)
    count = 0
    while count < 254:
        count += 1
        try:
            sok.do_handshake()
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

def _sendHttpHeaders(sok, method, request, headers):
    data = _requestLine(method, request)
    if headers:
        data += ''.join('%s: %s\r\n' % i for i in headers.items())
    data += '\r\n'
    yield _asyncSend(sok, data)

def _requestLine(method, request):
    return "%s %s HTTP/1.1\r\n" % (method, request)

def _asyncSend(sok, data):
    while data != "":
        size = sok.send(data)
        data = data[size:]
        yield

POOL_REFACTOR_ME = SocketPool()