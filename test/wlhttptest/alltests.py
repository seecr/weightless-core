#!/usr/bin/env python2.5
#

import platform, sys
if not platform.python_version() >= "2.5":
	print "Needed python 2.5 or higher."
	sys.exit(1)

sys.path.insert(0, '../../src')

import unittest

#from wlhttprequesttest import WlHttpRequestTest
from wlhttpresponsetest import WlHttpResponseTest

if __name__ == '__main__':
	unittest.main()

