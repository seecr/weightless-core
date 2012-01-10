from unittest import TestCase, main
from weightless.core import compose
from weightless.core.utils import autostart

""" This code demonstrated the difficulties with callbacks and showed a simpler implementation with a generator.  Most of the value is in the dynamics of writing the code, not in staring at the end-result.  If you want to get the full value of it, throw away the code, start with implementing the first test, see how relatively simple the code is, then watch what you need to do in order to let the second test (which breaks the header in two messages) succeed: how complicated the callback based handler becomes.
Then proceed to the generatorBasedHTTPHandler() and see how this is a simple lineair piece of code, and how it remains lineair and simple while fixing it for making the second test (with a broken-up heade) succeed.
As a third step, the code for joining multiple network buffers into one buffer (readUntilEOL) is extracted into a separate generator, which can only be 'included' if you use @compose.

The example deals with data from a network and turn it into a simple HTTP call such as handle(method, type, body)"""

class CallBackBasedHTTPHandler(object):

    def __init__(self, handler):
        self._handler = handler
        self._method = None
        self._fragment = ''
        self._expected = 'POST'

    def send(self, data):
        if data.startswith(self._expected) and not self._method:
            self._method = data[:4]
            self._expected = 'Content-Type'
        elif data.startswith(self._expected) and self._method:
            self._fragment += data
            while not self._fragment.endswith('\r\n'):
                self._expected = ''
                return
            self._contenttype = self._fragment.split(': ')[1].strip()
            self._expected = '\r\n'
        elif data.startswith('\r\n'):
            self._expected = ''
        else:
            self._body = data
            self._handler(self._method, self._contenttype, self._body)

@autostart
@compose
def generatorBasedHTTPHandler(handler):
    request = yield
    method = request[:4]
    header = yield readUntilEOL()
    contenttype = header.split(': ')[1].strip()
    eoh = yield
    body = yield
    handler(method, contenttype, body)
    yield

def readUntilEOL():
    fragment = yield
    while not fragment.endswith('\r\n'):
        fragment += (yield)
    raise StopIteration(fragment)


class CallbackTest(TestCase):
    """ the tests are in reverse order """

    def testGeneratorWithBrokenUpHeader(self):
        result = []
        def httphandler(*args):
            result.extend(args)
        handler = generatorBasedHTTPHandler(httphandler)
        handler.send('POST / HTTP/1.0\r\n')
        handler.send('Content-Type: te')  # break header
        handler.send('xt/plain\r\n')
        handler.send('\r\n')
        handler.send('Hello Pythons!')
        self.assertEquals(['POST', 'text/plain', 'Hello Pythons!'], result)

    def testGenerator(self):
        result = []
        def httphandler(*args):
            result.extend(args)
        handler = generatorBasedHTTPHandler(httphandler)
        handler.send('POST / HTTP/1.0\r\n')
        handler.send('Content-Type: text/plain\r\n')
        handler.send('\r\n')
        handler.send('Hello Pythons!')
        self.assertEquals(['POST', 'text/plain', 'Hello Pythons!'], result)

    def testCallbacksWithBrokenUpHeader(self):
        result = []
        def httphandler(*args):
            result.extend(args)
        handler = CallBackBasedHTTPHandler(httphandler)
        handler.send('POST / HTTP/1.0\r\n')
        handler.send('Content-Type: te')  # break header
        handler.send('xt/plain\r\n')
        handler.send('\r\n')
        handler.send('Hello Pythons!')
        self.assertEquals(['POST', 'text/plain', 'Hello Pythons!'], result)

    def testCallbacks(self):
        result = []
        def httphandler(*args):
            result.extend(args)
        handler = CallBackBasedHTTPHandler(httphandler)
        handler.send('POST / HTTP/1.0\r\n')
        handler.send('Content-Type: text/plain\r\n')
        handler.send('\r\n')
        handler.send('Hello Pythons!')
        self.assertEquals(['POST', 'text/plain', 'Hello Pythons!'], result)

main()
