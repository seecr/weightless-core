## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
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

from types import GeneratorType, FunctionType

def decorator(generatorOrFunction):
    if type(generatorOrFunction) == GeneratorType:
        print "composing"
        return generatorOrFunction
    elif type(generatorOrFunction) == FunctionType:
        print "decorating"
        return generatorOrFunction
    else:
        print "error"

class A(object):
    @decorator
    def f(self):
        yield

g0 = A().f()
g1 = decorator(A().f())


