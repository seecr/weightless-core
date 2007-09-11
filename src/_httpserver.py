from _acceptor import Acceptor
from weightless.http.spec import REGEXP, FORMAT, HTTP
from socket import SHUT_RDWR

RECVSIZE = 4096

def HttpServer(reactor, port, generatorFactory, timeout=1):
    """Factory that creates a HTTP server listening on port, calling generatorFactory for each new connection.  When a client does not send a valid HTTP request, it is disconnected after timeout seconds. The generatorFactory is called with the HTTP Status and Headers as arguments.  It is expected to return a generator that produces the response -- including the Status line and Headers -- to be send to the client."""
    return Acceptor(reactor, port, lambda sok: HttpHandler(reactor, sok, generatorFactory, timeout))

class HttpHandler(object):

    def __init__(self, reactor, sok, generatorFactory, timeout):
        self._reactor = reactor
        self._sok = sok
        self._generatorFactory = generatorFactory
        self._request = ''
        self._rest = None
        self._timeout = timeout
        self._timer = None

    def __call__(self):
        kwargs = {}
        self._request += self._sok.recv(RECVSIZE)
        match = REGEXP.REQUEST.match(self._request)
        if not match:
            # this creates multiple timers, must not do that
            self._timer = self._reactor.addTimer(self._timeout, self._badRequest)
            return # for more data
        if self._timer:
            self._reactor.removeTimer(self._timer)
            self._timer = None
        request = match.groupdict()
        headers = {}
        for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(request['_headers']):
            headers[fieldname.title()] = fieldvalue.strip()
        del request['_headers']
        request['Headers'] = headers
        self._handler = self._generatorFactory(**request)
        self._reactor.removeReader(self._sok)
        self._reactor.addWriter(self._sok, self._writeResponse)

    def _badRequest(self):
        self._sok.send('HTTP/1.0 400 Bad Request\r\n\r\n')
        self._sok.shutdown(SHUT_RDWR)
        self._sok.close()

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
