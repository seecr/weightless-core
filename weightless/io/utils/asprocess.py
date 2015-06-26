## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2015 Seecr (Seek You Too B.V.) http://seecr.nl
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
from types import FunctionType

from weightless.core import compose, Yield, identify, is_generator
from weightless.io import Reactor


def asProcess(g):
    """
    Facillitate scripting with Components, DNA, and other async jazz; without the headace.

    Accepts a generator, composes and runs is using a Reactor's addProcess and loop, quits loop and returns the async return-value at end-of-generator.
    """
    def _asProcess(g):
        if not is_generator(g):
            raise TypeError("asProcess() expects a generator, got %s" % repr(g))

        reactor = Reactor()  # Between creating and reactor.loop() there should be no statements that can raise exceptions (otherwise (epoll) fd-leaking occurs).
        wrapper(g, reactor)
        try:
            reactor.loop()
        except StopIteration, e:
            if e.args:
                return e.args[0]

    @identify
    def wrapper(generator, reactor):
        this = yield
        reactor.addProcess(process=this.next)
        try:
            yield
            g = compose(generator)
            while True:
                _response = g.next()
                if _response is Yield:
                    continue
                if _response is not Yield and callable(_response):
                    _response(reactor, this.next)
                    yield
                    _response.resumeProcess()
                yield
        finally:
            reactor.removeProcess(process=this.next)

    if type(g) == FunctionType:  # asProcess used as decorator
        @wraps(g)
        def helper(*args, **kwargs):
            return _asProcess(g(*args, **kwargs))
        return helper
    return _asProcess(g)

