from unittest import TestCase
from random import randint
from time import sleep
from socket import socket
from threading import Thread
from weightless import HttpReader, Reactor

def server(port, response, request):
    def serverProcess():
        serverSok = socket()
        serverSok.bind(('0.0.0.0', port))
        serverSok.listen(1)
        newSok, addr = serverSok.accept()
        request.append(newSok.recv(4096))
        newSok.send(response)
        newSok.close()
        serverSok.close()

    thread=Thread(None, serverProcess)
    thread.start()
    sleep(0.01) # yield
    return thread

class ReaderTest(TestCase):

    def testRequestAndHeaders(self):
        HttpReader.RECVSIZE = 7
        port = randint(2**10, 2**16)
        request = []
        serverThread = server(port, "HTTP/1.1 200 OK\r\ncOnteNt-type: text/html\r\n\r\nHello World!", request)
        def receiveResponse(reader, HTTPVersion=None, StatusCode=None, ReasonPhrase=None, Headers=None):
            self.dataReceived = HTTPVersion, StatusCode, ReasonPhrase, Headers
        reactor = Reactor()
        reader = HttpReader(reactor, 'http://localhost:%s/aap/noot/mies' % port, receiveResponse)
        for i in range(8): reactor.step()
        self.assertEquals('GET /aap/noot/mies HTTP/1.0\r\nHost: localhost\r\nUser-Agent: Weightless/v0.1\r\n\r\n', request[0])
        serverThread.join()
        self.assertEquals(('1.1', '200', 'OK', {'Content-Type': 'text/html'}), self.dataReceived)

    def testGetAllData(self):
        HttpReader.RECVSIZE = 7
        fragments = []
        port = randint(2**10, 2**16)
        serverThread = server(port, "HTTP/1.1 200 OK\r\ncOnteNt-type: text/html\r\n\r\nHello World!", [])
        def receiveFragment(fragment):
            fragments.append(fragment)
        def receiveResponse(reader, HTTPVersion=None, StatusCode=None, ReasonPhrase=None, Headers=None):
            reader.receiveFragment(receiveFragment)
        reactor = Reactor()
        reader = HttpReader(reactor, 'http://localhost:%s/aap/noot/mies' % port, receiveResponse)
        for i in range(9): reactor.step()
        serverThread.join()
        self.assertEquals('Hello World!', ''.join(fragments))

    def testNoPort(self):
        fragments = []
        done = []
        def receiveFragment(fragment):
            if fragment == None:
                done.append(True)
            else:
                fragments.append(fragment)
        def receiveResponse(reader, HTTPVersion=None, StatusCode=None, ReasonPhrase=None, Headers=None):
            self.dataReceived = HTTPVersion, StatusCode, ReasonPhrase, Headers
            reader.receiveFragment(receiveFragment)
        reactor = Reactor()
        reader = HttpReader(reactor, 'http://www.cq2.org/', receiveResponse)
        while not done:
            reactor.step()
        self.assertEquals('302', self.dataReceived[1])
        self.assertEquals('Found', self.dataReceived[2])
        self.assertEquals('close', self.dataReceived[3]['Connection'])
        self.assertEquals('<p>The document has moved <a href="/page/softwarestudio.page/show">here</a></p>\n', ''.join(fragments))

    def testOpenerRssFeed(self):
        fragments = []
        done = []
        def receiveFragment(fragment):
            if fragment == None:
                done.append(True)
            else:
                fragments.append(fragment)

        def receiveResponse(reader, HTTPVersion=None, StatusCode=None, ReasonPhrase=None, Headers=None):
            self.dataReceived = HTTPVersion, StatusCode, ReasonPhrase, Headers
            reader.receiveFragment(receiveFragment)

        reactor = Reactor()
        reader = HttpReader(reactor, "http://www.opener.ou.nl/rss_all", receiveResponse)
        while not done:
            reactor.step()

        self.assertTrue('<dc:subject>managementwetenschappen</dc:subject>' in ''.join(fragments))