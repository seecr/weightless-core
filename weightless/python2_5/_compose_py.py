## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from platform import python_version
assert python_version() >= "2.5", "Python 2.5 required"

from types import GeneratorType
from sys import exc_info
try:
    from tbtools import inject_traceback
except ImportError:
    from warnings import warn
    warn('inject_traceback not available, continuing without generator-tracebacks')
    def inject_traceback(*args, **kwargs):
        pass

def compose(initial):
    """
    The method compose() allows program (de)composition with generators.  It enables calls like:
        retvat = yield otherGenerator(args)
    The otherGenerator may return values by:
        yield RETURN, retvat, remaining data
    Remaining data might be present if the otherGenerator consumes less than it get gets.  It must
    make this remaining data available to the calling generator by yielding it as shown.
    Most notably, compose enables catching exceptions:
        try:
            retvat = yield otherGenerator(args)
        except Exception:
            pass
    This will work as expected: it catches an exception thrown by otherGenerator.
    """
    generators = [initial]
    messages = [None]
    exception = None
    while generators:
        generator = generators[-1]
        try:
            if exception:
                response = generator.throw(exception[1])
                exception = None
            else:
                message = messages.pop(0)
                response = generator.send(message)
            if type(response) == GeneratorType:
                generators.append(response)
                frame = response.gi_frame
                assert frame, 'Generator is exhausted.'
                assert frame.f_lineno == frame.f_code.co_firstlineno, 'Generator already used.'
                messages.insert(0, None)
            elif response or not messages:
                try:
                    message = yield response
                    assert not (message and response), 'Cannot accept data. First send None.'
                    messages.append(message)
                    if response and messages[0] is not None:
                        messages.insert(0, None)
                except Exception:
                    exType, exValue, exTraceback = exc_info()
                    exception = exType, exValue, None
        except StopIteration, returnValue:
            exception = None
            generators.pop()
            if returnValue.args:
                messages = list(returnValue.args) + messages
            else:
                messages.insert(0, None)
        except AssertionError:
            raise # testing support
        except Exception:
            generators.pop()
            exType, exValue, exTraceback = exc_info()
            # if this is the same exception, keep and extend the previous traceback.
            if exception and id(exValue) == id(exception[1]) and exception[2]:
                inject_traceback(exception[2], exTraceback.tb_next, 0)
            else:
                exception = exType, exValue, exTraceback
    if exception:
        raise exception[0], exception[1], exception[2].tb_next
