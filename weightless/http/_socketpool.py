## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2015 Koninklijke Bibliotheek (KB) http://www.kb.nl
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

import sys
from socket import SHUT_RDWR
from time import time
from traceback import print_exc

from weightless.core import compose, identify


class SocketPool(object):
    """
    Minimal SocketPool implementation.

    No maximum on:
     - total poolsize
     - per destination pooled size

    Further:
     - Re-uses oldest connections first (FIFO)
     - does not sanity-check sockets (socket errors, fd-errors, read-with-pushback checks)
    """

    def __init__(self, reactor, unusedTimeout=None):
        self._reactor = reactor
        self._unusedTimeout = unusedTimeout
        self._pool = {}

        if unusedTimeout is not None:
            self._initUnusedTimeout()

    def getPooledSocket(self, host, port):
        key = (host, port)
        socks = self._pool.get(key)
        if socks is None:
            return

        try:
            raise StopIteration(socks.pop(0)[0])
        except IndexError:
            del self._pool[key]
            return
            yield

    def putSocketInPool(self, host, port, sock):
        # Expects a socket *object*, not a file-descriptor!
        key = (host, port)
        self._pool.setdefault(key, []).append((sock, time()))
        return
        yield

    def _initUnusedTimeout(self):
        @identify
        @compose
        def unusedTimeout():
            this = yield
            try:
                while True:
                    self._reactor.addTimer(seconds=self._unusedTimeout, callback=this.next)
                    yield  # Wait for timer

                    # Purge idle sockets
                    now = time()
                    unusedTimeout = self._unusedTimeout
                    for (host, port), _list in self._pool.items():
                        for t in _list[:]:
                            sock, putTime = t
                            if now > (putTime + unusedTimeout):
                                _list.remove(t)
                                try:
                                    sock.shutdown(SHUT_RDWR)
                                except (AssertionError, KeyboardInterrupt, SystemExit):
                                    raise
                                except Exception:
                                    pass  # Cleanup, not interested in socket / fd errors here.
                                sock.close()
            except (AssertionError, KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                sys.stderr.write("Unexpected exception in SocketPool's unusedTimeout:\n'")
                print_exc()
                raise AssertionError("Unexpected exception, failing")

        unusedTimeout()

