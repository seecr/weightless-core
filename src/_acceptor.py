from socket import socket, AF_INET, SOCK_STREAM

class Acceptor(object):

    def __init__(self, port, reactor, sinkFactory):
        sok = socket(AF_INET, SOCK_STREAM)
        sok.bind(('0.0.0.0', port))
        sok.listen(1)
        reactor.addReader(sok, self.accept)
        self.sinkFactory = sinkFactory

    def accept(self, reactor, sok):
        newConnection, address = sok.accept()
        reactor.addReader(newConnection, self.sinkFactory(reactor, newConnection))