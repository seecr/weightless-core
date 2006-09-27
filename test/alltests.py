#!/usr/bin/python2.5
#
import platform, sys
if not platform.python_version() >= "2.5":
	print "Needed python 2.5 or higher."
	sys.exit(0)

sys.path.append('../src')
sys.setcheckinterval(sys.maxint)

import unittest

from wlthreadtest import WlStatusTest
#from wlfiletest import WlFileTest
#from wlselecttest import WlSelectTest
#from wlthreadpooltest import WlThreadPoolTest
#from wlsockettest import WlSocketTest
#from wlservicetest import WlServiceTest

if __name__ == '__main__':
	unittest.main()

