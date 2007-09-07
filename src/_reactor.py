from traceback import print_exc
from select import select

class Reactor(object):

    def __init__(self, select_func = select):
        self._readers = {}
        self._writers = {}
        self._timers = []
        self._select = select_func

    def loop(self):
        while True:
            self.step()

    def step(self):
        timeout = None
        if self._timers:
            timeout, timerCallback = self._timers[-1]
        selectResult = self._select(self._readers.keys(), self._writers.keys(), [], timeout)

        if selectResult == ([],[],[]):
            timerCallback()
            self._timers.pop()

        rReady, wReady, ignored = selectResult
        for sok in rReady:
            try:
                self._readers[sok]()
            except:
                print_exc()
        for sok in wReady:
            try:
                self._writers[sok]()
            except:
                print_exc()

    def addReader(self, sok, sink):
        self._readers[sok] = sink

    def addWriter(self, sok, source):
        self._writers[sok] = source

    def addTimer(self, seconds, callback):
        self._timers.append((seconds, callback))
        self._timers = sorted(self._timers, lambda (second1, callback1), (second2, callback2): cmp(second2, second1))

    def removeReader(self, sok):
        del self._readers[sok]

    def removeWriter(self, sok):
        del self._writers[sok]


