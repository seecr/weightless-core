#!/usr/bin/env python

from weightless.core import be 
from weightless.io import Reactor, Server
from weightless.httpng import HttpProtocol, http

class HelloWorld(object):
    def processRequest(self, *args, **kwargs):
        yield http.ok()
        yield http.headers('Content-Length', 6)
        yield 'Hello!'

reactor = Reactor()

dna = \
    (Server(reactor, 8080),
        (HttpProtocol(),
            (HelloWorld(),)
        )
    )

server = be(dna)
reactor.loop()
