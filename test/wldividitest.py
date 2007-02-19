from unittest import TestCase
from types import GeneratorType

from weightless import WlDict, WlComponent

class WlDividiTest(TestCase):
	def setUp(self):
		self.sink = None
		class Interceptor(WlComponent):
			def notify(inner, message):
				self.message = message
				return self.sink
		self.interceptor = Interceptor()

	def testNotify(self):
		class MyComponent(WlComponent):
			def notify(self, value):
				return 'my sink'
		component = MyComponent()
		sink = component.notify(WlDict())
		self.assertEquals('my sink', sink)

	def  testChanged(self):
		component1 = WlComponent()
		component1.addObserver(self.interceptor)
		component1.changed('a value')
		self.assertEquals('a value', self.message)

	def tessssssssstChangedWithReturnedSink(self):
		class MyComponent(WlComponent):
			def notify(self, value): return 'my sink'
		component1 = MyComponent()
		component1.addObserver(self.interceptor)
		self.sink = 'my sink'
		sink = component1.changed('n/a')
		self.assertEquals('my sink', sink)

	def tesssstChangedWithReturnedSinkCombined(self):
		class MyComponent(WlComponent):
			def notify(self, value):
				return (x for x in ['aap'])
		comp1 = MyComponent()
		comp2 = MyComponent()
		comp3 = MyComponent()
		comp1.addObserver(comp2)
		comp1.addObserver(comp3)
		retval = comp1.changed({})
		self.assertEquals(GeneratorType, type(retval))
		self.assertEquals(['aap', 'aap'], list(retval))