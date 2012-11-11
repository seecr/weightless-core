from unittest import TestCase
import gc
from weightless.core import compose
from weightless.core import AllMessage, AnyMessage, DoMessage, OnceMessage
from types import GeneratorType

#gc.set_debug(gc.DEBUG_LEAK)

class GCTestCase(TestCase):

    def setUp(self):
        super(GCTestCase, self).setUp()
        gc.collect()
        self._baseline = self.get_tracked_objects()

    def tearDown(self):
        super(GCTestCase, self).tearDown()
        def tostr(o):
            if isframe(o):
                return getframeinfo(o)
            try:
                return tostring(o)
            except:
                return repr(o)
        gc.collect()
        diff = set(self.get_tracked_objects()) - set(self._baseline)
        self.assertEquals(set(), diff)
        for obj in diff:
            print "Leak:"
            print tostr(obj)
            print "Referrers:"
            for o in gc.get_referrers(obj):
                print tostr(o)
        del self._baseline
        gc.collect()

    def get_tracked_objects(self):
        return [o for o in gc.get_objects() if type(o) in 
                (compose, GeneratorType, Exception,
                    AllMessage, AnyMessage, DoMessage, OnceMessage)]
 
