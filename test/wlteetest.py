from unittest import TestCase

from weightless import wlTee

class WlTeeTest(TestCase):

	def testSimple(self):
		g1 = (x for x in 'apno')
		g2 = (x for x in 'a ot')
		g = wlTee(g1, g2)
		response = ''.join(list(g))
		self.assertEquals('aap noot', response)

	def testOneGeneratorStopsBeforeTheOther(self):
		g1 = (x for x in 'apno is')
		g2 = (x for x in 'a otme')
		g = wlTee(g1, g2)
		response = ''.join(list(g))
		self.assertEquals('aap noot mies', response, 'What to do is this case?')

	def testSend(self):
		data = []
		def f1():
			data.append((yield ''))
		def f2():
			data.append((yield ''))
		g = wlTee(f1(), f2())
		g.next()
		try: g.send('duplicate me')
		except StopIteration: pass
		self.assertEquals(['duplicate me', 'duplicate me'], data)