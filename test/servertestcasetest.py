from __future__ import with_statement
from servertestcase import ServerTestCase
from socket import socket

class ServerTestCaseTest(ServerTestCase):

    def testWithRealSocket(self):
        with self.server(['response one', 'response two']) as (port, messages):
            client = socket()
            client.connect(('127.0.0.1', port))
            client.send('aap')
            response = client.recv(999)
            self.assertEquals('response one', response)
            client.send('noot')
            response = client.recv(999)
            self.assertEquals('response two', response)
        self.assertEquals('aap', messages[0])
        self.assertEquals('noot', messages[1])

