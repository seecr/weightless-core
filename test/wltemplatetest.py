from unittest import TestCase
from weightless.wlcompose_old import compose
from weightless import Template

class WlTemplateTest(TestCase):

	def testSimpleData(self):
		t = Template('here is <%=1+2%> text')
		line = t.next()
		self.assertEquals('here is ', line)
		line = t.next()
		self.assertEquals('3', line)
		line = t.next()
		self.assertEquals(' text', line)

	def testSymbol(self):
		t = Template('here is <%=2*localSymbol%> text', {'localSymbol': 3})
		result = ''.join(t)
		self.assertEquals('here is 6 text', result)

	def testAssingmentToLocal(self):
		t = Template('here <%symbol=4%>is <%=symbol*2%> text')
		result = ''.join(t)
		self.assertEquals('here is 8 text', result)

	def testCannotImport(self):
		t = Template('here is <%=import httplib%> text')
		try:
			result = ''.join(t)
			self.fail()
		except SyntaxError, e:
			self.assertEquals('invalid syntax (<template>, line 1)', str(e))

	def testCallBuiltins(self):
		t = Template('here is <%=max(1,2,3)%> text')
		result = ''.join(t)
		self.assertEquals('here is 3 text', result)

	def testCallBuiltinsNOT(self):
		t = Template('here is <%=open("/tmp")%> text')
		try:
			result = ''.join(t)
			self.fail()
		except NameError, e:
			self.assertEquals("name 'open' is not defined", str(e))

	def testSimpleLoopWithGeneratorExpression(self):
		t = Template('results:\n<%=("number %d is here\\n" % n for n in range(3))%>')
		result = ''.join(compose(t))
		self.assertEquals('results:\nnumber 0 is here\nnumber 1 is here\nnumber 2 is here\n', result)

	def testPerformance(self):
		from timeit import Timer
		t = Timer("list(Template('here is <%=max(1,2,3)%> text'))", "from weightless import Template").timeit(1000)
		self.assertTrue(0 < t < 0.05, t) # t in ms must remain under 20.000 times/second

