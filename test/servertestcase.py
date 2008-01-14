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

