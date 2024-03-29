## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
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

from socket import socket, timeout
from time import sleep
from threading import Thread, Event

def server(port, response, expectedrequest, delay=0, loop=50):
    isListening = Event()
    expectedrequest = expectedrequest.encode() if type(expectedrequest) is str else expectedrequest
    def serverProcess():
        serverSok = socket()
        serverSok.bind(('0.0.0.0', port))
        serverSok.listen(1)
        isListening.set()
        newSok, addr = serverSok.accept()
        newSok.settimeout(1)

        msg = b''
        for i in range(loop):
            if expectedrequest:
                try:
                    msg += newSok.recv(4096)
                    if msg == expectedrequest:
                        break
                    if len(msg) >= len(expectedrequest):
                        raise timeout
                except timeout:
                    print("Received:", repr(msg))
                    print("expected:", repr(expectedrequest))
                    return
        if response:
            if hasattr(response, '__next__'):
                for r in response:
                    newSok.send(r.encode())
            else:
                newSok.send(response.encode())
            sleep(delay)
        else:
            sleep(0.5)
        newSok.close()
        serverSok.close()

    thread = Thread(None, serverProcess)
    thread.daemon = True
    thread.start()
    isListening.wait()
    return thread
