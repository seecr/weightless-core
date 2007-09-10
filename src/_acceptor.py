from socket import socket

class Acceptor(object):
    """Listens on a port for incoming internet (TCP/IP) connections and calls a factory to create a handler for the new connection.  It does not use threads but a asynchronous reactor instead."""

    def __init__(self, reactor, port, sinkFactory):
        """The reactor is a user specified reactor for dispatching I/O events asynchronously. The sinkFactory is called with the newly created socket as its single argument. It is supposed to return a callable callback function that is called by the reactor when data is available."""
        sok = socket()
        sok.bind(('0.0.0.0', port))
        sok.listen(1)
        reactor.addReader(sok, self._accept)
        self._sinkFactory = sinkFactory
        self._sok = sok
        self._reactor = reactor

    def _accept(self):
        newConnection, address = self._sok.accept()
        self._reactor.addReader(newConnection, self._sinkFactory(newConnection))