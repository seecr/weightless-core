
class Suspend(object):
    def __call__(self, reactor):
        print 'hier ben ik niet hoor'
        reactor.suspend()
        self._reactor = reactor
