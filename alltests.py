#!/usr/bin/env python
#
import platform, sys
if not platform.python_version() >= "2.5":
	print "Needed python 2.5 or higher."
	sys.exit(0)

import unittest

from wlthreadtest import WlThreadTest
from wlscheduletest import WlScheduleTest
from wlselecttest import WlSelectTest
from wlstreamtest import WlStreamTest

if __name__ == '__main__':
	unittest.main()

