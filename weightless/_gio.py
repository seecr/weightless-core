from weightless import compose

python_open = open

class Gio(object):

    def __init__(self, reactor, eventGenerator):
        self._eventGenerator = compose(eventGenerator)
        self._reactor = reactor
        self._continue(None)

    def _continue(self, value):
        try:
            event = self._eventGenerator.send(value)
            event(self._reactor, self._continue)
        except StopIteration:
            pass

class open(object):

    def __init__(self, uri, mode='r'):
        self._uri = uri
        self._mode = mode

    def __call__(self, reactor, continuation):
        self._sok = python_open(self._uri, self._mode)
        self.fileno = self._sok.fileno
        continuation(self)

    def read(self):
        return _read(self)

    def write(self, data):
        return _write(self, data)

    def close(self):
        return _close(self)

class _read(object):

    def __init__(self, sok):
        self._sok = sok._sok

    def __call__(self, reactor, continuation):
        self._reactor = reactor
        self._continuation = continuation
        reactor.addReader(self._sok, self._doread)

    def _doread(self):
        self._reactor.removeReader(self._sok)
        self._continuation(self._sok.read())

class _write(object):

    def __init__(self, sok, data):
        self._sok = sok._sok
        self._data = data

    def __call__(self, reactor, continuation):
        self._reactor = reactor
        self._continuation = continuation
        reactor.addWriter(self._sok, self._dowrite)

    def _dowrite(self):
        self._reactor.removeWriter(self._sok)
        self._continuation(self._sok.write(self._data))

class _close(object):

    def __init__(self, sok):
        self._sok = sok

    def __call__(self, reactor, continuation):
        continuation(self._sok.close())