from weightless import Suspend, identify
from socket import socket, error

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
    sok = socket()
    sok.setblocking(0)
    try:
        sok.connect((host, port))
    except error, errno:
        print errno # should be (115, 'Operation now in progress')
    reactor.addWriter(sok, this.next)
    yield
    print 'connected'
    yield
    reactor.removeWriter(sok)
    sok.send('GET / HTTP/1.1\r\n\r\n')
    reactor.addReader(sok, this.next)
    yield
    response = sok.recv(999)
    reactor.removeReader(sok)
    sok.close()
    resume(response)
    yield


def httpget(host, port, *args):
    s = MySuspend(doGet(host, port).send)
    yield s 
    raise StopIteration(s.response)
