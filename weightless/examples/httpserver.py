#!/usr/bin/env python

from weightless import Reactor, Server, HttpProtocol, be, http

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
