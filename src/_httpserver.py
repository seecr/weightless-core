from _acceptor import Acceptor
from weightless.http.spec import REGEXP, FORMAT, HTTP
from socket import SHUT_RDWR

class Handler(object):

    def __init__(self, reactor, sok, generator):
        self._reactor = reactor
        self._sok = sok
        self._generator = generator
        self._request = ''
        self._rest = None

    def __call__(self):
        kwargs = {}
        self._request += self._sok.recv(HttpServer.RECVSIZE)
        match = REGEXP.REQUEST.match(self._request)
        if not match:
            return # for more data
        request = match.groupdict()
        headers = {}
        for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(request['_headers']):
            headers[fieldname.title()] = fieldvalue.strip()
        del request['_headers']
        request['Headers'] = headers
        self._handler = self._generator(**request)
        self._reactor.removeReader(self._sok)
        self._reactor.addWriter(self._sok, self._writeResponse)

    def _writeResponse(self):
        try:
            if self._rest:
                data = self._rest
            else:
                data = self._handler.next()
            sent = self._sok.send(data)
            if sent < len(data):
                self._rest = data[sent:]
            else:
                self._rest = None
        except StopIteration:
            self._reactor.removeWriter(self._sok)
            self._sok.shutdown(SHUT_RDWR)
            self._sok.close()

class HttpServer:

    RECVSIZE = 4096

    def __init__(self, reactor, port, callback):
        self._reactor = reactor
        self._callback = callback
        self._acceptor = Acceptor(reactor, port, self._handlerFactory)

    def _handlerFactory(self, sok):
        return Handler(self._reactor, sok, self._callback)