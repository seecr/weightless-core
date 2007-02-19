from wltee import wlTee

class Observable:
	def __init__(self):
		self._observers = []
	def addObserver(self, observer):
		self._observers.append(observer)
	def changed(self, value):
		return wlTee([observer.notify(value) for observer in self._observers])

class WlComponent(Observable):
	pass