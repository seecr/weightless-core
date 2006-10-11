@contextmanager
def running(function):
	t = Thread(None, function)
	t.start()
	yield t
	t.join()
