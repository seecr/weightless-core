from contextlib import contextmanager

@contextmanager
def running(function):
    t = Thread(None, function)
    t.start()
    yield t
    t.join()

class Dict(object):
	def __init__(self, dict = None):
		if dict is not None:
			self.__dict__ = dict