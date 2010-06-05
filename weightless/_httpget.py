from weightless import Suspend, identify
from socket import socket

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
    sok.connect((host, port)) # must become asynchronous, since DNS can block!
    reactor.addWriter(sok, this.next)
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
