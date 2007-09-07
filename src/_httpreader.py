from socket import socket
from urlparse import urlsplit
from weightless.http.spec import REGEXP, FORMAT, HTTP

class HttpReader(object):

    RECVSIZE = 4096

    def __init__(self, reactor, url, callback):
        scheme, host, path, query, fragment = urlsplit(url)
        port = '80'
        if ':' in host:
            host, port = host.split(':')
        self._responseBuffer = ''
        self._restData = None
        self._callback = callback
        self._sok = socket()
        self._sok.connect((host, int(port)))
        self._reactor = reactor
        self._reactor.addWriter(self._sok, lambda: self._sendRequest(path, host))

    def _sendRequest(self, path, host):
        sent = self._sok.send(
            FORMAT.RequestLine % {'Method': 'GET', 'Request_URI': path}
            + FORMAT.HostHeader % {'Host': host}
            + FORMAT.UserAgentHeader
            + HTTP.CRLF)
        self._reactor.removeWriter(self._sok)
        self._reactor.addReader(self._sok, self._headerFragment)

    def _headerFragment(self):
        self._responseBuffer += self._sok.recv(HttpReader.RECVSIZE)
        match = REGEXP.RESPONSE.match(self._responseBuffer)
        if not match:
            return #for more data
        if match.end() < len(self._responseBuffer):
            self._restData = self._responseBuffer[match.end():]
        request = match.groupdict()
        headers = {}
        for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(request['_headers']):
            headers[fieldname.title()] = fieldvalue.strip()
        del request['_headers']
        request['Headers'] = headers
        self._callback(self, **request)

    def receiveFragment(self, callback):
        if self._restData:
            callback(self._restData)
            self._restData = None
        self._callback = callback
        self._reactor.removeReader(self._sok)
        self._reactor.addReader(self._sok, self._bodyFragment)

    def _bodyFragment(self):
        fragment = self._sok.recv(HttpReader.RECVSIZE)
        if not fragment:
            self._reactor.removeReader(self._sok)
            self._sok.close()
            self._callback(None)
        else:
            self._callback(fragment)
