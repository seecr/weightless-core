## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2015 Koninklijke Bibliotheek (KB) http://www.kb.nl
# Copyright (C) 2015, 2020-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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
from random import choice
from socket import SHUT_RDWR
from time import time
from traceback import print_exc

from weightless.core import Observable, compose, identify


class EmptySocketPool(object):
    """
    No-op implementation:
     - Always empty
     - putSocketInPool immediately shutdown & closes socket.
    """
    def getPooledSocket(self, host, port):
        return
        yield

    def putSocketInPool(self, host, port, sock):
        # Expects a socket *object*, not a file-descriptor!
        _shutAndCloseIgnorant(sock)
        return
        yield


class SocketPool(Observable):
    """
    Minimal SocketPool implementation.

    Further:
     - Re-uses oldest connections first (FIFO)
     - does not sanity-check sockets (socket errors, fd-errors, read-with-pushback checks)
    """

    def __init__(self, reactor, unusedTimeout=None, limits=None, **kwargs):
        Observable.__init__(self, **kwargs)
        self._reactor = reactor
        self._unusedTimeout = unusedTimeout
        self._limitTotalSize = limits.get(_TOTAL_SIZE) if limits else None
        self._limitDestinationSize = limits.get(_DESTINATION_SIZE) if limits else None
        self._pool = {}
        self._poolSize = 0

        if limits and not set(limits.keys()).issubset(_LIMITS):
            raise TypeError('limits argument options must be one of: ' + ', '.join(_LIMITS))

        if unusedTimeout is not None:
            self._initUnusedTimeout()

    def getPooledSocket(self, host, port):
        key = (host, port)
        socks = self._pool.get(key)
        if socks is None:
            return

        try:
            s = socks.pop()[0]
            self._poolSize -= 1
            return s
        except IndexError:
            del self._pool[key]
            return
            yield

    def putSocketInPool(self, host, port, sock):
        # Expects a socket *object*, not a file-descriptor!
        key = (host, port)
        yield self._purgeSocksIfOversized(key)
        self._pool.setdefault(key, []).append((sock, time()))
        self._poolSize += 1
        return
        yield

    def _purgeSocksIfOversized(self, key):
        if self._limitDestinationSize is not None:
            destinationPool = self._pool.get(key)
            if destinationPool and len(destinationPool) >= self._limitDestinationSize:
                sock = destinationPool.pop(0)[0]
                self._poolSize -= 1
                _shutAndCloseIgnorant(sock)
                self.do.log(message="[SocketPool] destinationSize limit (%s) reached for: %s:%d\n" % (self._limitDestinationSize, key[0], key[1]))

        if (self._limitTotalSize is not None) and self._poolSize >= self._limitTotalSize:
            while True:
                host, port = choice(list(self._pool.keys()))
                sock = yield self.getPooledSocket(host=host, port=port)
                if sock:
                    _shutAndCloseIgnorant(sock)
                    self.do.log(message="[SocketPool] totalSize limit (%s) reached, removed socket for: %s:%d\n" % (self._limitTotalSize, host, port))
                    break

    def _initUnusedTimeout(self):
        @identify
        @compose
        def unusedTimeout():
            this = yield
            try:
                while True:
                    self._reactor.addTimer(seconds=self._unusedTimeout, callback=this.__next__)
                    yield  # Wait for timer

                    # Purge idle sockets
                    now = time()
                    unusedTimeout = self._unusedTimeout
                    for (host, port), _list in list(self._pool.items()):
                        for t in _list[:]:
                            sock, putTime = t
                            if now > (putTime + unusedTimeout):
                                _list.remove(t)
                                self._poolSize -= 1
                                _shutAndCloseIgnorant(sock)
            except (AssertionError, KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                sys.stderr.write("Unexpected exception in SocketPool's unusedTimeout:\n'")
                print_exc()
                raise AssertionError("Unexpected exception, failing")

        unusedTimeout()


def _shutAndCloseIgnorant(sock):
    try:
        sock.shutdown(SHUT_RDWR)
    except (AssertionError, KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass  # Cleanup, not interested in socket / fd errors here.
    sock.close()

_TOTAL_SIZE = 'totalSize'
_DESTINATION_SIZE = 'destinationSize'
_LIMITS = set([_TOTAL_SIZE, _DESTINATION_SIZE])
