## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015, 2018-2020 Seecr (Seek You Too B.V.) https://seecr.nl
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

from inspect import currentframe


def findInLocals(f_locals, localName):
    if localName in f_locals:
        return f_locals[localName]
    if '__callstack__' in f_locals:
        for generator in reversed(f_locals['__callstack__']):
            try:
                return findInLocals(generator.gi_frame.f_locals, localName)
            except AttributeError:
                pass
    raise AttributeError(localName) from None

def findLocalInFrame(frame, localName):
    while frame:
        try:
            return findInLocals(frame.f_locals, localName)
        except AttributeError:
            pass
        frame = frame.f_back

    raise AttributeError(localName) from None

def local(localName):
    frame = currentframe().f_back
    try:
        return findLocalInFrame(frame, localName)
    except AttributeError:
        raise AttributeError(localName) from None
