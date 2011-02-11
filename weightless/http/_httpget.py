## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from sys import exc_info
from weightless.http import Suspend
from weightless.core import identify
from socket import socket, error as SocketError, SOL_SOCKET, SO_ERROR, SHUT_WR, SHUT_RD
from errno import EINPROGRESS

@identify
def doGet(host, port, request, vhost=""):
    this = yield # this generator, from @identify
    suspend = yield # suspend object, from Suspend.__call__
    sok = socket()
    sok.setblocking(0)
    #sok.settimeout(1.0)
    try:
        sok.connect((host, port))
    except SocketError, (errno, msg):
        if errno != EINPROGRESS:
            raise
    suspend._reactor.addWriter(sok, this.next)
    yield
    try:
        err = sok.getsockopt(SOL_SOCKET, SO_ERROR)
        if err != 0:    # connection created succesfully?
            raise IOError(err)
        yield
        suspend._reactor.removeWriter(sok)
        # sendall() of loop gebruiken
        # error checking
        sok.send('%s\r\n' % _httpRequest(request, vhost=vhost))
        sok.shutdown(SHUT_WR)
        #sok.shutdown(WRITER)
        suspend._reactor.addReader(sok, this.next)
        responses = []
        while True:
            yield
            response = sok.recv(4096) # error checking
            if response == '':
                break
            responses.append(response)
        suspend._reactor.removeReader(sok)
        #sok.shutdown(READER)
        sok.close()
        suspend.resume(''.join(responses))
    except Exception, e:
        suspend.throw(*exc_info())
    yield

def _httpRequest(request, vhost=""):
    httpRequest = "GET %s HTTP/1.0\r\n" % request
    if vhost != "":
        httpRequest = "GET %s HTTP/1.1\r\nHost: %s\r\n" % (request, vhost)
    return httpRequest


def httpget(host, port, request, vhost=""):
    s = Suspend(doGet(host, port, request, vhost=vhost).send)
    yield s
    result = s.getResult()
    raise StopIteration(result)
