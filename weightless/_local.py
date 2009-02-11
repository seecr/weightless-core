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
from weightless import reactor

class local(object):

    def __init__(self):
        object.__setattr__(self, '_reactor', None)

    def _getReactor(self):
        if self._reactor == None:
            object.__setattr__(self, '_reactor', reactor())
        return self._reactor

    def __getattr__(self, name):
        context = self._getReactor().currentcontext
        return context.locals[name]

    def __setattr__(self, name, attr):
        context = self._getReactor().currentcontext
        context.locals[name] = attr

