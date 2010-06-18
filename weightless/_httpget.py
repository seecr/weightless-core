from weightless import Suspend, identify
from socket import socket, error as SocketError, SOL_SOCKET, SO_ERROR
from errno import EINPROGRESS
from traceback import print_exc

class MySuspend(Suspend):
    def __init__(self, doNext):
        self._doNext = doNext
        self._exception = None
    def __call__(self, reactor, whenDone):
        #super(MySuspend, self).__call__(reactor)
        self._reactor = reactor
        try:
            self._doNext(self)
        except Exception, e:
            self._exception = e
            print_exc()
        else:
            self._whenDone = whenDone
            self._handle = reactor.suspend()
    def resume(self, response):
        self._response = response
        self._whenDone()
    def throw(self, exception):
        self._exception = exception
        self._whenDone()
    def resumeWriter(self):
        if hasattr(self, "_handle"):
            self._reactor.resumeWriter(self._handle)
    def getResult(self):
        if self._exception:
            raise self._exception
        return self._response


@identify
def doGet(host, port, request):
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
        sok.send('GET %s HTTP/1.1\r\n\r\n' % request) # + Host of HTTP 1.0
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
        suspend.throw(e)
    yield


def httpget(host, port, request):
    s = MySuspend(doGet(host, port, request).send)
    data = yield s
    result = s.getResult()
    raise StopIteration(result)
