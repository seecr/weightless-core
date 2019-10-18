from functools import wraps
from sys import exc_info

from weightless.core import identify
from weightless.io import reactor


def dieAfter(seconds=5.0):
    """
    Decorator for generator-function passed to asProcess to execute; for setting deadline.
    """
    def dieAfter(generatorFunction):
        @wraps(generatorFunction)
        @identify
        def helper(*args, **kwargs):
            this = yield
            yield  # Works within an asProcess-passed generatorFunction only (needs contextual addProcess driving this generator and a reactor).
            tokenList = []
            def cb():
                tokenList.pop()
                this.throw(AssertionError, AssertionError('dieAfter triggered after %s seconds.' % seconds), None)
            tokenList.append(reactor().addTimer(seconds=seconds, callback=cb))
            try:
                retval = yield generatorFunction(*args, **kwargs)
            except:
                c, v, t = exc_info()
                if tokenList:
                    reactor().removeTimer(token=tokenList[0])
                raise v.with_traceback(t)
        return helper
    return dieAfter
