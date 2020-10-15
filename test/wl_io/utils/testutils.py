## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2020 Seecr (Seek You Too B.V.) https://seecr.nl
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
                this.throw(AssertionError(AssertionError('dieAfter triggered after %s seconds.' % seconds)).with_traceback(None))
            tokenList.append(reactor().addTimer(seconds=seconds, callback=cb))
            try:
                retval = yield generatorFunction(*args, **kwargs)
            except:
                c, v, t = exc_info()
                if tokenList:
                    reactor().removeTimer(token=tokenList[0])
                raise c(v).with_traceback(t)
        return helper
    return dieAfter
