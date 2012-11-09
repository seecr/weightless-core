from utils import candidates
from utils import methodOrMethodPartialStr
from sys import exc_info
from types import GeneratorType

def is_generator(o):
    return type(o) == GeneratorType

class DeclineMessage(Exception):
    """Should be thrown by a component that wishes to opt out of a 
    message received through 'any' or 'call' that it can't or doesn't
    wish to handle after all.
    
    One reason might be that none of this components' observers responds
    to the message after being 'forwarded' (as signalled by a 
    NoneOfTheObserversRespond exception). For an example, please refer
    to the code of Transparent below."""
    
class NoneOfTheObserversRespond(Exception):
    """Must not be thrown anywhere outside of the Observable
    implementation. It is exposed only so that it can be caught in 
    specific components, typically to be able to opt out of some 
    received message by raising DeclineMessage."""

    def __init__(self, unansweredMessage, nrOfObservers):
        Exception.__init__(self, 'None of the %d observers respond to %s(...)' % (nrOfObservers, unansweredMessage))

class MessageBase(object):
    def __init__(self, observers, message):
        __slot__ = ('_message', '_methods', '_nrOfObservers')
        self._message = message
        self._methods = tuple(candidates(observers, message, self.altname))
        self._nrOfObservers = len(tuple(observers))

    def all(self, *args, **kwargs):
        for method in self._methods:
            try:
                result = method(*args, **kwargs)
                self.verifyMethodResult(method, result)
                _ = yield result
            except DeclineMessage:
                continue
            except:
                c, v, t = exc_info(); raise c, v, t.tb_next
            assert _ is None, "%s returned '%s'" % (methodOrMethodPartialStr(method), _)

    def any(self, *args, **kwargs):
        try:
            for r in self.all(*args, **kwargs):
                try:
                    result = yield r
                    raise StopIteration(result)
                except DeclineMessage:
                    continue
        except:
            c, v, t = exc_info(); raise c, v, t.tb_next
        raise NoneOfTheObserversRespond(
                unansweredMessage=self._message, nrOfObservers=self._nrOfObservers)

    def verifyMethodResult(self, method, result):
        assert is_generator(result), "%s should have resulted in a generator." % methodOrMethodPartialStr(method)

