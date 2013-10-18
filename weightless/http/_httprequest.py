## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2013 Seecr (Seek You Too B.V.) http://seecr.nl
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
from weightless.io import Suspend
from weightless.core import compose, identify
from socket import socket, error as SocketError, SOL_SOCKET, SO_ERROR
from errno import EINPROGRESS
from ssl import wrap_socket, SSL_ERROR_WANT_READ, SSL_ERROR_WANT_WRITE, SSLError

@identify
@compose
def _do(method, host, port, request, body=None, headers=None, ssl=False, callback=None):
    headers = headers or {}
    this = yield # this generator, from @identify
    suspend = yield # suspend object, from Suspend.__call__
    sok = socket()
    sok.setblocking(0)
    try:
        sok.connect((host, port))
    except SocketError, (errno, msg):
        if errno != EINPROGRESS:
            raise

    if ssl:
        suspend._reactor.addWriter(sok, this.next)
        yield
        suspend._reactor.removeWriter(sok)

        sok = wrap_socket(sok, do_handshake_on_connect=False)
        while True:
            try:
                sok.do_handshake()
                break
            except SSLError as err:
                if err.args[0] == SSL_ERROR_WANT_READ:
                    suspend._reactor.addReader(sok, this.next)
                    yield
                    suspend._reactor.removeReader(sok)
                elif err.args[0] == SSL_ERROR_WANT_WRITE:
                    suspend._reactor.addWriter(sok, this.next)
                    yield
                    suspend._reactor.removeWriter(sok)

    suspend._reactor.addWriter(sok, this.next)
    yield
    try:
        err = sok.getsockopt(SOL_SOCKET, SO_ERROR)
        if err != 0:    # connection created succesfully?
            suspend._reactor.removeWriter(sok)
            raise IOError(err)
        yield
        # error checking
        if body:
            data = body
            if type(data) is unicode:
                data = data.encode(getdefaultencoding())
            headers.update({'Content-Length': len(data)})
        try:
            yield _sendHttpHeaders(sok, method, request, headers)
            if body:
                yield _asyncSend(sok, data)
        finally:
            suspend._reactor.removeWriter(sok)
        suspend._reactor.addReader(sok, this.next)
        responses = []
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

            if callback:
                callback(response)
            else:
                responses.append(response)
        suspend._reactor.removeReader(sok)
        sok.close()
        suspend.resume(None if callback else ''.join(responses))
    except Exception:
        suspend.throw(*exc_info())
    yield

def _httpRequest(method, request):
    return "%s %s HTTP/1.0\r\n" % (method, request)

def _asyncSend(sok, data):
    while data != "":
        size = sok.send(data)
        data = data[size:]
        yield

def _sendHttpHeaders(sok, method, request, headers):
    data = _httpRequest(method, request)
    if headers:
        data += ''.join('%s: %s\r\n' % i for i in headers.items())
    data += '\r\n'
    yield _asyncSend(sok, data)

def httpget(host, port, request, headers=None, callback=None):
    s = Suspend(_do('GET', host, port, request, headers=headers, callback=callback).send)
    yield s
    result = s.getResult()
    raise StopIteration(result)

def httppost(host, port, request, body, headers=None):
    s = Suspend(_do('POST', host, port, request, body, headers=headers).send)
    yield s
    result = s.getResult()
    raise StopIteration(result)

def httpsget(host, port, request, headers=None):
    s = Suspend(_do('GET', host, port, request, headers=headers, ssl=True).send)
    yield s
    result = s.getResult()
    raise StopIteration(result)

def httpspost(host, port, request, body, headers=None):
    s = Suspend(_do('POST', host, port, request, body, headers=headers, ssl=True).send)
    yield s
    result = s.getResult()
    raise StopIteration(result)
