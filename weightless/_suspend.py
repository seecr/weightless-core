
class Suspend(object):
    def __call__(self, reactor):
        self._handle = reactor.suspend()
        self._reactor = reactor

    def resumeWriter(self):
        self._reactor.resumeWriter(self._handle)
