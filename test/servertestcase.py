## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
from __future__ import with_statement

from unittest import TestCase
from threading import Thread, Event
from socket import socket
from contextlib import contextmanager
from random import randint

class ServerTestCase(TestCase):

    @contextmanager
    def server(self, responses, bufsize=4096):
        port = randint(2**10, 2**16)
        start = Event()
        messages = []
        def serverThread():
            s = socket()
            s.bind(('127.0.0.1', port))
            s.listen(0)
            start.set()
            connection, address = s.accept()
            for response in responses:
                msg = connection.recv(bufsize)
                messages.append(msg)
                connection.send(response)
            connection.close()
        thread = Thread(None, serverThread)
        thread.start()
        start.wait()
        yield port, messages
        thread.join()

