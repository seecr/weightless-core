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

import sys
from errno import EINPROGRESS
from functools import partial
from socket import socket, error as SocketError, SOL_SOCKET, SO_ERROR, SHUT_RDWR, SOL_TCP, TCP_KEEPINTVL, TCP_KEEPIDLE, TCP_KEEPCNT, SO_KEEPALIVE
from ssl import wrap_socket, SSL_ERROR_WANT_READ, SSL_ERROR_WANT_WRITE, SSLError
from sys import exc_info, getdefaultencoding
from urlparse import urlsplit

from weightless.core import compose, identify, Observable
from weightless.io import Suspend, TimeoutException
from weightless.http import REGEXP, parseHeaders


# TODO:
# - should retry failed requests on pooled sockets


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


@identify
@compose
def _do(observable, method, host, port, request, body=None, headers=None, secure=False, prio=None):
    headers = headers or {}
    retryOnce = False
    shutAndCloseOnce = _NOOP
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
            retryOnce = True
        else:
            sok = yield _createSocket(host, port, secure, this, suspend, prio)
        shutAndCloseOnce = _shutAndCloseOnce(sok)

        ## Send Request-Line and Headers.
        suspend._reactor.addWriter(sok, this.next, prio=prio)
        try:
            yield
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

        ## Read response (& handle 100 Continue #fail)
        suspend._reactor.addReader(sok, this.next, prio=prio)
        try:
            parsedHeader, body, doClose = yield _readHeaderAndBody(sok)
        finally:
            suspend._reactor.removeReader(sok)

        ## Either put socket in a pool or close when we must.
        if doClose:
            shutAndCloseOnce()
        else:
            suspend._reactor.addProcess(process=this.next, prio=prio)
            try:
                yield observable.any.putSocketInPool(host=host, port=port, sock=sok)
            finally:
                suspend._reactor.removeProcess(process=this.next)
        suspend.resume((parsedHeader, body))
    except (AssertionError, KeyboardInterrupt, SystemExit):
        raise
    except TimeoutException:
        pass
    except Exception:
        suspend.throw(*exc_info())
    finally:
        shutAndCloseOnce(ignoreExceptions=True)  # If there is a socket, close it sooner rather than later (at GC).
    yield  # wait for GC


def _createSocket(host, port, secure, this, suspend, prio):
    # No "yield", so add*/remove* not needed.
    sok = socket()
    sok.setblocking(0)
    sok.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)
    sok.setsockopt(SOL_TCP, TCP_KEEPIDLE, 60*10)
    sok.setsockopt(SOL_TCP, TCP_KEEPINTVL, 75)
    sok.setsockopt(SOL_TCP, TCP_KEEPCNT, 9)
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
    raise StopIteration(sok)

def _getOrCreateSocket(host, port, secure, pool, this, suspend, prio):
    suspend._reactor.addProcess(process=this.next, prio=prio)
    yield  # First "yield <data>" since start-of-composed & (this/g).send(<SuspendObj>).  After this yield, Suspend._whenDone filled-in and thus throwing is safe again.
    try:
        sok = pool.get(host, port)
        if sok:
            raise StopIteration((True, sok))  # fromPool, <sok>

        sok = _OLDcreateSocket()
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

    if secure:
        sok = yield _sslHandshake(sok, this, suspend, prio)
    raise StopIteration((False, sok))  # fromPool, <sok>


def _OLDcreateSocket():
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
    # TODO: add Host header iff not given
    data = _requestLine(method, request)
    if headers:
        data += ''.join('%s: %s\r\n' % i for i in headers.items())
    data += '\r\n'
    yield _asyncSend(sok, data)

def _requestLine(method, request):
    return "%s %s HTTP/1.1\r\n" % (method, request)

def _readHeaderAndBody(sok):
    # TODO: cannot produce sensible 'response' from invalid/incomplete server response.
    parsedHeader, rest = yield _readHeader(sok)
    body, doClose = yield _readBody(sok, rest)
    raise StopIteration((parsedHeader, body, doClose))

def _readHeader(sok, rest=''):
    responses = rest
    rest = ''
    while True:
        response = yield _asyncRead(sok)
        if response is _CLOSED:
            raise ValueError('Premature close')  # TODO: handle this.
        responses += response

        match = REGEXP.RESPONSE.match(responses)
        if not match:
            # TODO: check some max. statusline + header size (or bail).
            continue

        # Matched:
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

def _readBody(sok, rest):
    responses = rest  # Must be empty-string at least
    doClose = False
    while True:
        response = yield _asyncRead(sok)
        if response is _CLOSED:
            doClose = True
            break
        responses += response
    raise StopIteration((responses, doClose))

def _asyncSend(sok, data):
    while data != "":
        size = sok.send(data)
        data = data[size:]
        yield

def _asyncRead(sok):
    while True:
        yield
        try:
            response = sok.recv(4096) # error checking
        except SSLError as e:
            if e.errno != SSL_ERROR_WANT_READ:
                raise
            continue

        if response == '':
            raise StopIteration(_CLOSED)
        raise StopIteration(response)

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

def _NOOP():
    pass

_CLOSED = type('CLOSED', (object,), {})()
