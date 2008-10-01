from unittest import TestCase

from weightless.http import httpspec

class HttpSpecTest(TestCase):
    def testParseHeader(self):
        self.assertEquals(('aap', {}), httpspec.parseHeader('aap'))
        self.assertEquals(('aap', {'noot': 'mies'}), httpspec.parseHeader('aap; noot=mies'))
        self.assertEquals(('aap', {'noot': 'mies', 'vis': 'vuur'}), httpspec.parseHeader('aap; noot=mies; vis=vuur'))