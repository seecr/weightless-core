## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2007 Seek You Too B.V. (CQ2) http://www.cq2.nl
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

RETURN = 1

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
                response = generator.throw(exception)
                exception = None
            else:
                message = messages.pop(0)
                response = generator.send(message)
            if type(response) == GeneratorType:
                generators.append(response)
                messages.insert(0, None)
            elif type(response) == tuple:
                messages = list(response) + messages
            elif response or not messages:
                try:
                    message = yield response
                    messages.append(message)
                except Exception, ex:
                    exception = ex
        except StopIteration, returnValue:
            generators.pop()
            if returnValue.args:
                messages = list(returnValue.args) + messages
            if not messages:
                messages.append(None)
        except Exception, ex:
            generators.pop()
            exception = ex
    if exception:
        raise exception
