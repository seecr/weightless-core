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
class TransparentSocket(object):
    def __init__(self, originalObject, logFile = None):
        self._originalObject = originalObject
        self._logFile = logFile
        self._lastMethod = None

    def __getattr__(self, attrname):
        return getattr(self._originalObject, attrname)

    def __hasattr__(self, attrname):
        return hasattr(self._originalObject, attrname)

    def _logString(self, method, data):
        if self._logFile:
            f = open(self._logFile, 'a')
            try:
                if method != self._lastMethod:
                    f.write("\n%s:\n" % method)
                    self._lastMethod = method
                f.write(data)
            finally:
                f.close()

    def recv(self, bytes, *args, **kwargs):
        result = self._originalObject.recv(bytes, *args, **kwargs)
        self._logString('recv', result)
        return result

    def send(self, data, *args, **kwargs):
        bytesSent = self._originalObject.send(data, *args, **kwargs)
        self._logString("send", data[:bytesSent])
        return bytesSent

    def sendall(self, data, *args, **kwargs):
        self._logString("send", data)
        return self._originalObject.sendall(data, *args, **kwargs)
