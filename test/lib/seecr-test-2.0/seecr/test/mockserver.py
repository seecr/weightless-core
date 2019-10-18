## begin license ##
#
# "Seecr Test" provides test tools.
#
# Copyright (C) 2012, 2015 Seecr (Seek You Too B.V.) http://seecr.nl
#
# This file is part of "Seecr Test"
#
# "Seecr Test" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Seecr Test" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Seecr Test"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from sys import stdout
from socket import socket, SOL_SOCKET, SO_REUSEADDR, SO_LINGER, AF_INET, SOCK_STREAM, IPPROTO_TCP
from struct import pack
from select import select
from time import sleep
from threading import Thread
from urllib.parse import urlsplit, parse_qs

# _httpspec is originally from Weightless (http://weightless.io)
from ._httpspec import REGEXP, parseHeaders


class MockServer(Thread):
    def __init__(self, port, ipAddress='0.0.0.0', hangupConnectionTimeout=None):
        Thread.__init__(self)
        self.daemon = True
        address = (ipAddress, port)
        self.socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
        self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.socket.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
        self.socket.bind(address)
        self.socket.listen(5)

        self.myUrl = 'http://%s:%s' % address
        self.response = None
        self.responses = []
        self.requests = []
        self.halt = False

        # Accept a connection, wait some time, then close.
        self.hangupConnectionTimeout = hangupConnectionTimeout

    def run(self):
        while True:
            r,w,e = select([self.socket], [], [], 0.01)

            if self.halt:
                break

            if self.socket in r:
                c, addr = self.socket.accept()
                if self.hangupConnectionTimeout is not None:
                    sleep(self.hangupConnectionTimeout)
                    c.close()
                    continue
                contentLength = None
                request = c.recv(4096)
                while True:
                    if not b'\r\n\r\n' in request:
                        request += c.recv(4096)
                        continue
                    if contentLength:
                        if contentLength > len(body):
                            request += c.recv(contentLength - len(body))
                            header, body = request.split(b'\r\n\r\n')
                        break
                    header, body = request.split(b'\r\n\r\n')
                    for h in header.split(b'\r\n'):
                        if h.startswith(b'Content-Length'):
                            contentLength = int(h.split(b':')[1])
                    if not contentLength:
                        break

                self.requests.append(request)

                match = REGEXP.REQUEST.match(request)
                RequestURI = match.group('RequestURI').decode('ascii')
                scheme, netloc, path, query, fragments = urlsplit(RequestURI)
                Host, port = None, None
                if netloc:
                    Host, _, port = netloc.partition(':')
                    port = int(port) if port else None
                arguments = parse_qs(query, keep_blank_values=True)
                Headers = parseHeaders(match.group('_headers'))

                response = self.buildResponse(
                    request=request,
                    RequestURI=RequestURI,
                    scheme=scheme,
                    netloc=netloc,
                    Host=Host,
                    port=port,
                    path=path,
                    query=query,
                    fragments=fragments,
                    arguments=arguments,
                    Headers=Headers,
                    Body=body)
                c.send(_maybeEncodeAsUtf8(response))
                c.close()

        self.socket.close()

    def buildResponse(self, **kwargs):
        if not self.response is None:
            return self.response
        if self.responses:
            return self.responses.pop(0)
        return 'HTTP/1.0 500 Internal server error\r\n\r\nMockServer ran out of responses.'


def _maybeEncodeAsUtf8(in_):
    if type(in_) != str:
        return in_

    return in_.encode()
