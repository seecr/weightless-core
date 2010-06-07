from weightless import Suspend, identify
from socket import socket, error as SocketError, SOL_SOCKET, SO_ERROR
from errno import EINPROGRESS

class MySuspend(Suspend):
    def __init__(self, doNext):
        self._doNext = doNext
        self._exception = None
    def __call__(self, reactor):
        super(MySuspend, self).__call__(reactor)
        self._doNext(self)
    def resume(self, response):
        self._response = response
        self.resumeWriter()
    def throw(self, exception):
        self._exception = exception
        self.resumeWriter()
    def done(self):
        if self._exception:
            raise self._exception
        raise StopIteration(self._response)



@identify
def doGet(host, port):
    this = yield # this generator, from @identify
    suspend = yield
    try:
        sok = socket()
        sok.setblocking(0)
        try:
            sok.connect((host, port))
        except SocketError, (errno, msg):
            if errno != EINPROGRESS:
                raise
        suspend._reactor.addWriter(sok, this.next)
        yield
        err = sok.getsockopt(SOL_SOCKET, SO_ERROR)
        if err != 0:    # connection created succesfully?
            raise IOError(err)
        yield
        suspend._reactor.removeWriter(sok)
        sok.send('GET / HTTP/1.1\r\n\r\n')
        suspend._reactor.addReader(sok, this.next)
        yield
        response = sok.recv(999)
        suspend._reactor.removeReader(sok)
        sok.close()
        suspend.resume(response)
    except Exception, e:
        suspend.throw(e)
    yield


def httpget(host, port, *args):
    s = MySuspend(doGet(host, port).send)
    yield s
    s.done()
