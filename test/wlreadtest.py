from unittest import TestCase
from weightless import WlGenerator

from re import compile
def Read(regexp, vars):
	regExp = compile(regexp)
	match = None
	data = ''
	while not match:
		data = data + (yield None)
		print data
		match = regExp.search(data)
	print match
	end = match.end()
	vars.__dict__.update(match.groupdict())
	restData = data[end:]

class WlReadTest(TestCase):

	def testOne(self):
		class Container: pass
		data = []
		def sink(vars):
			yield Read(r'some(?P<var>.*)stuff', vars)
			while True:
				buff = yield None
				data.append(buff)
		vars = Container()
		g = WlGenerator(sink(vars))
		g.next()
		g.send('wrong stuff')
		g.send(' ignore some go')
		g.send('od stuff and the rest ')
		g.send('is here')
		self.assertEquals(' good ', vars.var)
		self.assertEquals(' and the rest', data[0])
