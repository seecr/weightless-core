## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
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

from functools import partial as curry
from time import time

def f(a):
    b = a

t0 = time()

for i in range(10**6):
    f('a')

t1 = time()
print('Function call sec', t1-t0, 'us 100%')

for i in range(10**6):
    curry(f, 'a')()

t2 = time()
print('With Curry', t2-t1, 'us', (t2-t1)/(t1-t0)*100, '%')

def f(a):
    yield
    b = a

for i in range(10**6):
    next(f('a'))

t3 = time()
print('With Generator', t3-t2, 'us', (t3-t2)/(t1-t0)*100, '%')

class f:
    def __init__(self, a):
        self.a = a
    def __call__(self):
        b = self.a

for i in range(10**6):
    f('a')()

t4 = time()
print('With Class', t4-t3, 'us', (t4-t3)/(t1-t0)*100, '%')