from socket import socket, AF_INET, SOCK_STREAM

class Acceptor(object):

    def __init__(self, reactor, port, sinkFactory):
        sok = socket(AF_INET, SOCK_STREAM)
        sok.bind(('0.0.0.0', port))
        sok.listen(1)
        reactor.addReader(sok, self.accept)
        self.sinkFactory = sinkFactory
        self._sok = sok
        self._reactor = reactor

    def accept(self):
        newConnection, address = self._sok.accept()
        self._reactor.addReader(newConnection, self.sinkFactory(newConnection))