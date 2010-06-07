from weightless import Suspend, identify
from socket import socket, error as SocketError, SOL_SOCKET, SO_ERROR
from errno import EINPROGRESS

class MySuspend(Suspend):
    def __init__(self, doNext):
        self._doNext = doNext
    def __call__(self, reactor):
        super(MySuspend, self).__call__(reactor)
        self._doNext(reactor)
        self._doNext(self.resume)
    def resume(self, response):
        self.response = response
        self.resumeWriter()


@identify
def doGet(host, port):
    this = yield # this generator, from @identify
    reactor = yield # reactor, from MySuspend.__call__
    resume = yield # resume callback, from MySuspend.__call__
    try:
        sok = socket()
        sok.setblocking(0)
        try:
            sok.connect((host, port))
        except SocketError, (errno, msg):
            if errno != EINPROGRESS:
                raise
        reactor.addWriter(sok, this.next)
        yield
        err = sok.getsockopt(SOL_SOCKET, SO_ERROR)
        if err != 0:    # connection created succesfully?
            raise IOError(err)
        yield
        reactor.removeWriter(sok)
        sok.send('GET / HTTP/1.1\r\n\r\n')
        reactor.addReader(sok, this.next)
        yield
        response = sok.recv(999)
        reactor.removeReader(sok)
        sok.close()
        resume(response)
    except Exception, e:
        resume(str(e)) # do something else here: raise it at client somehow
    yield


def httpget(host, port, *args):
    s = MySuspend(doGet(host, port).send)
    yield s 
    raise StopIteration(s.response)
