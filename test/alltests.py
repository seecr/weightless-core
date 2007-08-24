#!/usr/bin/env python2.5
#

import platform, sys
if not platform.python_version() >= "2.5":
	print "Needed python 2.5 or higher."
	sys.exit(1)

sys.path.insert(0, '..')

import unittest

from wlthreadtest import WlStatusTest, WlPoolTest
from wlsockettest import WlSocketTest, WlFileSocketTest, WlListenTest, WlSelectTest, WlAsyncProcessorTest
from wlservicetest import WlServiceTest
from wlcomposetest import WlComposePythonTest, WlComposePyrexTest
from wlhttptest import WlHttpRequestTest, WlHttpResponseTest
from wldividitest import WlDividiTest
from wlteetest import WlTeeTest
from wldicttest import WlDictTest
from wltemplatetest import WlTemplateTest

if __name__ == '__main__':
	unittest.main()

