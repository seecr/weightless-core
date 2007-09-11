from traceback import print_exc
from select import select
from time import time
import os

def cmpTimer((second1, callback1), (second2, callback2)):
    return cmp(second2, second1)

class Reactor(object):

    def __init__(self, select_func = select):
        self._readers = {}
        self._writers = {}
        self._timers = []
        self._select = select_func

    def loop(self):
        """Calls step() endlessly."""
        while True:
            self.step()

    def step(self):
        """Performs one single select and calls handlers on active sockets."""
        timeout = None
        if self._timers:
            timer = self._timers[-1]
            setTime, timerCallback = timer
            timeout =  max(0, setTime - time())
            if timeout == 0:
                self._timers.remove(timer)
                try:
                    timerCallback()
                except:
                    print_exc()
                timeout = None
                return

        #print self._readers, self._writers, self._timers
        selectResult = self._select(self._readers.keys(), self._writers.keys(), [], timeout)

        if selectResult == ([],[],[]):
            try:
                timerCallback()
            except:
                print_exc()
            self._timers.remove(timer)

        rReady, wReady, ignored = selectResult
        for sok in rReady:
            try:
                self._readers[sok]()
            except:
                print_exc()
                del self._readers[sok]
        for sok in wReady:
            try:
                self._writers[sok]()
            except:
                print_exc()
                del self._writers[sok]

    def addReader(self, sok, sink):
        """Adds a socket and calls sink() when the socket becomes readable. It remains at the readers list."""
        self._readers[sok] = sink

    def addWriter(self, sok, source):
        """Adds a socket and calls source() whenever the socket is writable. It remains at the writers list."""
        self._writers[sok] = source

    def addTimer(self, seconds, callback):
        """Add a timer that calls callback() after the specified number of seconds. Afterwards, the timer is deleted.  It returns a token for removeTimer()."""
        assert seconds > 0, 'Timeout must be greater than 0. It was %s.' % seconds
        timer = (time()+seconds, callback)
        self._timers.append(timer)
        self._timers.sort(cmpTimer)
        return timer

    def removeReader(self, sok):
        """Removes a sockets callback from the readers list."""
        del self._readers[sok]

    def removeWriter(self, sok):
        """Removes a sockets callback from the writers list."""
        del self._writers[sok]

    def removeTimer(self, token):
        """Removes a timer.  The token is a token as returned by addTimer"""
        self._timers.remove(token)

    def shutdown(self):
        """Closes all readers and writers."""
        for sok in self._readers: sok.close()
        for sok in self._writers: sok.close()
