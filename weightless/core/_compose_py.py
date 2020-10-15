## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015, 2018-2020 Seecr (Seek You Too B.V.) https://seecr.nl
# Copyright (C) 2015 Koninklijke Bibliotheek (KB) http://www.kb.nl
#
# This file is part of "Weightless"
#
# "Weightless" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Weightless" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Weightless"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from sys import exc_info
from weightless.core import cpython, is_generator

"""
Wrt exceptions, see http://www.python.org/doc/2.5.4/lib/module-exceptions.html for Python 2.5:

BaseException
 +-- SystemExit                 sys.exit(), must exit, not an error, triggers finally's
 +-- KeyboardInterrupt          ctrl-c, must exit, not an error, triggers finally's
 +-- Exception                  built-in, non-system-exiting + user-defined exceptions
      +-- GeneratorExit         when close() called, not an error ==> will move
      +-- StopIteration         next() when no more values, not an error
      +-- StandardError
      |    +-- AssertionError   when assert statement fails ==> will move
      |    +-- ...
      +-- Warning
           +-- RuntimeWarning
           +-- ...

and http://docs.python.org/3.0/library/exceptions.html for Python 3.0:

BaseException
 +-- SystemExit             sys.exit(), must exit, not an error, triggers finally's
 +-- KeyboardInterrupt      ctrl-c, must exit
 +-- GeneratorExit          when close() called, not an error <== moved
 +-- Exception
      +-- StopIteration
      +-- AssertionError    when assert statement fails <== moved
      +-- Warning
           +-- RuntimeWarning
           +-- ...

"""

class Yield(object):
    """Sentinel for compose stepping"""
    def __new__(self):
        raise TypeError("cannot create 'Yield' instances")

def compose(initial, stepping=False):
    if not is_generator(initial):
        raise TypeError("compose() expects generator")
    return _compose(initial, stepping)

def _compose(initial, stepping):
    """
    The method compose() allows program (de)composition with generators.  It enables calls like:
        retvat = yield otherGenerator(args)
    The otherGenerator may return values by:
        return retval, remaining data
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
    __callstack__ = generators # make these visible to 'local()'
    messages = [None]
    exception = None
    while generators:
        generator = generators[-1]
        try:
            if exception:
                if exception[0] == GeneratorExit:
                    generator.close()
                    raise exception[1]
                response = generator.throw(*exception)
                exception = None
            else:
                message = messages.pop(0)
                response = generator.send(message)
            if is_generator(response):
                generators.append(response)
                frame = response.gi_frame
                if cpython: assert frame, 'Generator is exhausted.'
                if cpython: assert frame.f_lineno == frame.f_code.co_firstlineno, 'Generator already used.'
                try:
                    if stepping:
                        _ = yield Yield
                except BaseException:
                    exType, exValue, exTraceback = exc_info()
                    exception = (exType, exValue, exTraceback.tb_next)
                    continue
                if stepping: assert _ is None, 'Cannot accept data when stepping. First send None.'
                messages.insert(0, None)
            elif (response is not None) or not messages:
                try:
                    message = yield response
                    assert message is None or response is None, 'Cannot accept data. First send None.'
                    messages.insert(0, message)
                except BaseException:
                    exType, exValue, exTraceback = exc_info()
                    exception = (exType, exValue, exTraceback.tb_next)
        except StopIteration as returnValue:
            exception = None
            generators.pop()
            retval = returnValue.args
            if type(retval) is tuple and len(retval) == 1 and type(retval[0]) is tuple:
                retval = retval[0]
            if retval:
                messages[0:0] = retval
            else:
                generators and messages.insert(0, None)

        except BaseException:
            generators.pop()
            exType, exValue, exTraceback = exc_info()
            exception = (exType, exValue, exTraceback.tb_next)
    if exception:
        raise exception[1].with_traceback(exception[2])
    if len(messages) == 0:
        return None
    return messages[0] if len(messages) == 1 else tuple(messages)
