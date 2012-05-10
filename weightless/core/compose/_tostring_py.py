## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
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

from linecache import getline
from types import GeneratorType

def tostring(generator):
    if type(generator) != GeneratorType:
        raise TypeError("tostring() expects generator")
    frame = generator.gi_frame
    glocals = frame.f_locals
    lineno = frame.f_lineno
    code = frame.f_code
    name = code.co_name
    if name == "_compose":
        if 'generators' in glocals:
            return '\n'.join(tostring(g) for g in glocals['generators'])
        else:
            return tostring(glocals['initial'])
    filename = code.co_filename
    codeline = getline(filename, lineno).strip()
    return '  File "%(filename)s", line %(lineno)d, in %(name)s\n    %(codeline)s' % locals()
