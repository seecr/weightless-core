#!/usr/local/bin/python2.5
#
import platform, sys
if not platform.python_version() >= "2.5":
	print "Needed python 2.5 or higher."
	sys.exit(0)

sys.path.insert(0, '..')

import unittest

from wlthreadtest import WlStatusTest, WlPoolTest
from wlsockettest import WlSocketTest, WlFileSocketTest, WlListenTest, WlSelectTest
from wlservicetest import WlServiceTest
from wlgeneratortest import WlGeneratorTest
#from wlreadtest import WlReadTest
from wlhttptest import WlHttpRequestTest

if __name__ == '__main__':
	unittest.main()

