#!/usr/bin/env python2.5
## begin license ##
#
#    "Weightless" is a package with a wide range of valuable tools.
#    Copyright (C) 2005, 2006 Seek You Too B.V. (CQ2) http://www.cq2.nl
#
#    This file is part of "Weightless".
#
#    "Weightless" is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    "Weightless" is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with "Weightless"; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
from unittest import TestCase
from weightless import compose, Template

class TemplateTest(TestCase):

	def testSimpleData(self):
		t = Template('here is <%=1+2%> text')
		line = t.next()
		self.assertEquals('here is ', line)
		line = t.next()
		self.assertEquals(3, line)
		line = t.next()
		self.assertEquals(' text', line)

	def testSymbol(self):
		t = Template('here is <%=str(2*localSymbol)%> text', {'localSymbol': 3})
		result = ''.join(t)
		self.assertEquals('here is 6 text', result)

	def testAssingmentToLocal(self):
		t = Template('here <%symbol=4%>is <%=str(symbol*2)%> text')
		result = ''.join(t)
		self.assertEquals('here is 8 text', result)

	def testAssingmentMoreComplicated(self):
		class Object(object): pass
		t = Template('here <% a.b=4 %>is <%= str(a.b * 2) %> text', {'a': Object()})
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
		t = Template('here is <%=str(max(1,2,3))%> text')
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

	def testMorePythonCode(self):
		template = """Work this <% a = '1'; b = '3'
if a: b = '2'
%>out!"""
		t = Template(template)
		result = ''.join(t)
		self.assertEquals('Work this out!', result)

	def testPerformance(self):
		from timeit import Timer
		t = Timer("list(Template('here is <%=max(1,2,3)%> text'))", "from weightless import Template").timeit(1000)
		self.assertTrue(0 < t < 0.05, t) # t in ms must remain under 20.000 times/second





	def testAndNowForSomethingCompletelyDifferent(self):
		template = """
def template(sets, prefixes, stamp, unique):
	'<oaimeta>'
	'<sets>'
	for set in sets:
		'<setSpec>%s</setSpec>' % set
	'</sets>'
	'<prefixes>'
	a=2*3
	yield str(a)
	for prefix in prefixes:
		'<prefix>%s</prefix>' % prefix
	'</prefixes>'
	'<stamp>%s</stamp>' % stamp
	'<unique>%019i</unique>' % unique
	'</oaimeta>'
"""
		source = []
		for line in template.split('\n'):
			try:
				if compile(line.strip(), line, 'eval') or eval(line.strip()):
					source.append(line.replace("'", "yield '", 1))
			except SyntaxError, e:
				source.append(line)
		source = '\n'.join(source)
		print source
		code = compile(source, '<template>', 'exec')
		vars = {}; eval(code, {}, vars)
		generator = vars['template']
		result = ''.join(generator(set(['1']), set(['dc', 'oai']), '19:34', 3))
		self.assertEquals('<oaimeta><sets><setSpec>1</setSpec></sets><prefixes><prefix>dc</prefix><prefix>oai</prefix></prefixes><stamp>19:34</stamp><unique>0000000000000000003</unique></oaimeta>', result)  # see for yourself
