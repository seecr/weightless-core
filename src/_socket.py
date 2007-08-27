#!/usr/bin/env python2.5
## begin license ##
#
#    "Weightless" is a package with a wide range of valuable tools.
#    Copyright (C) 2005, 2006 Seek You Too B.V. (CQ2) http://www.cq2.nl
#
#    This file is part of "Weightless".
#
#    "Weightless" is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    "Weightless" is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with "Weightless"; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
#
from types import GeneratorType
from socket import SOL_SOCKET, SO_RCVBUF, SHUT_RDWR
from functools import partial as curry
from weightless._select import WriteIteration, ReadIteration, SuspendIteration

from time import sleep

WRITE_ITERATION = WriteIteration()
READ_ITERATION = ReadIteration()
STOP_ITERATION = StopIteration()
SUSPEND_ITERATION = SuspendIteration()

class Socket:

    def __init__(self, sok):
        self._sok = sok
        self.fileno = sok.fileno
        self._recv = curry(sok.recv, sok.getsockopt(SOL_SOCKET, SO_RCVBUF) / 2)
        self._write_queue = []

    def close(self):
        #self._sok.shutdown(SHUT_RDWR) can fail if client closes first
        self._sok.close()

    def sink(self, generator, selector):
        assert all(x in dir(generator) for x in ('send', 'next', 'throw', 'close')), 'need generator'
        self._sink = generator
        self._selector = selector
        try:
            response = generator.next()
        except (StopIteration, GeneratorExit):
            raise ValueError('useless generator: exhausted at first next()')
        if isinstance(response, WlAsyncProcessor):
            response.start(self)
        elif response:
            self._write_queue.append(response)
            self._selector.add(self, 'w')
        else:
            self._selector.add(self, 'r')

    def readable(self):
        data = self._recv()
        if not data: # orderly socket shutdown
            self._sink.close()
            raise STOP_ITERATION
        else:
            response = self._sink.send(data)
            if isinstance(response, WlAsyncProcessor):
                response.start(self)
                raise SUSPEND_ITERATION
            if response:
                self._write_queue.append(response)
                raise WRITE_ITERATION

    def writable(self):
        dataToSend = self._write_queue[0]
        bytesSend = self._sok.send(dataToSend)
        a = 1
        b = 2
        if bytesSend < len(dataToSend):
            self._write_queue[0] = buffer(dataToSend, bytesSend)
        else:
            self._write_queue.pop(0)
        if not self._write_queue:
            response = self._sink.next()
            if isinstance(response, WlAsyncProcessor):
                response.start(self)
                raise SUSPEND_ITERATION
            if not response:
                raise READ_ITERATION
            self._write_queue.append(response)

    def async_completed(self, retval):
        try:
            response = self._sink.next()
        except (StopIteration, GeneratorExit):
            return
        if isinstance(response, WlAsyncProcessor):
            response.start(self)
        elif response:
            self._write_queue.append(response)
            self._selector.add(self, 'w')
        else:
            self._selector.add(self, 'r')

    def send(self, data):
        self._write_queue.append(data)