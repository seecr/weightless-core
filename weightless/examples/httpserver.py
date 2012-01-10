#!/usr/bin/env python
## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
# 
# This file is part of "Weightless"
# 
# "Weightless" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# "Weightless" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with "Weightless"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# 
## end license ##

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
