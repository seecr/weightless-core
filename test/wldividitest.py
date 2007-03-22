from unittest import TestCase
from types import GeneratorType

from weightless import WlDict, WlComponent

class MyComponent(WlComponent):
	def notify(self, *args, **kwargs):
		return (x for x in ['aap'])

class ErrorComponent(WlComponent):
	def notify(self, *args, **kwargs):
		raise Exception('error')

class WlDividiTest(TestCase):
	def setUp(self):
		self.sink = None
		self.undo = None
		self.undoException = None
		class Interceptor(WlComponent):
			def notify(inner,*args, **kwargs):
				self.message = args, kwargs
				return self.sink
			def undo(inner, *args, **kwargs):
				self.undo = args, kwargs
				if self.undoException: raise self.undoException
		self.interceptor = Interceptor()

	def testNotify(self):
		component = MyComponent()
		sink = component.notify(None)
		self.assertEquals('aap', sink.next())

	def  testChanged(self):
		component1 = WlComponent()
		component1.addObserver(self.interceptor)
		component1.changed('a value')
		self.assertEquals((('a value',), {}), self.message)

	def testChangedWithReturnedSink(self):
		component1 = MyComponent()
		component1.addObserver(self.interceptor)
		self.sink = 'my sink'
		sink = component1.changed('n/a')
		self.assertEquals('my sink', sink)

	def testChangedWithReturnedSinkCombined(self):
		comp1 = MyComponent()
		comp2 = MyComponent()
		comp3 = MyComponent()
		comp1.addObserver(comp2)
		comp1.addObserver(comp3)
		retval = comp1.changed({})
		self.assertEquals(GeneratorType, type(retval))
		self.assertEquals('aapaap', ''.join(retval))

	def testExceptionWithOneObserver(self):
		comp1 = MyComponent()
		comp2 = ErrorComponent()
		comp1.addObserver(comp2)
		try:
			comp1.changed({})
			self.fail()
		except Exception, e:
			self.assertEquals('error', str(e))

	def testExceptionWithTwoObservers(self):
		comp1 = MyComponent()
		comp3 = ErrorComponent()
		comp1.addObserver(self.interceptor)
		comp1.addObserver(comp3)
		try:
			comp1.changed({})
			self.fail('should raise error')
		except Exception, e:
			self.assertEquals('error', str(e))
		self.assertEquals( ((), {}), self.undo)

	def testAllBetsAreOffWhenUndoRaisesException(self):
		self.undoException = Exception("sorry I can't help")
		comp1 = MyComponent()
		comp2 = ErrorComponent()
		comp1.addObserver(self.interceptor)
		comp1.addObserver(comp2)
		try:
			comp1.changed({})
			self.fail('should raise error')
		except Exception, e:
			self.assertEquals("sorry I can't help", str(e))
