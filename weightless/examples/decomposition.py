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

from weightless.core import compose

print """ 1. calling generators """
def f():
    yield 'No'
    yield g()
    yield 'here'

def g():
    yield 'PUN'


p = f()

print p.next()
print p.next() #?
print p.next()

p = compose(f())

print p.next()
print p.next()
print p.next()


print """ 2. Catching exceptions """

def f():
    try:
        yield g()
    except ZeroDivisionError:
        yield 'Oops'

def g():
    yield 1/0 # oops

p = f()

print p.next()

p = compose(f())

print p.next()


print """ 3. fixing Stack Traces """

def f():
    yield g()
def g():
    yield h()
def h():
    yield 1/0 # Oops

# Trace: main -> f() -> g() -> h()

# Without tbtools: remove the tbtools symlink
p = compose(f())

print p.next()
def f():
    yield g()

def g():
    yield h()

def h():
    yield 1/0


p = compose(f())

p.next()
