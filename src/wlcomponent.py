from wltee import wlTee

class Observable:

	def __init__(self):
		self._observers = []

	def addObserver(self, observer):
		self._observers.append(observer)

	def changed(self, *args, **kwargs):
		if len(self._observers) == 1:
			return self._observers[0].notify(*args, **kwargs)
		generators = []
		for n, observer in enumerate(self._observers):
			try:
				generators.append(observer.notify(*args, **kwargs))
			except Exception, e:
				for observer in (self._observers[i] for i in range(n, -1, -1)):
					if hasattr(observer, 'undo'):
						observer.undo()
				raise
		return wlTee(generators)

class WlComponent(Observable):
	pass