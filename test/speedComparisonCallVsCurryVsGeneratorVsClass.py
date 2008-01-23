from functools import partial as curry
from time import time

def f(a):
    b = a

t0 = time()

for i in xrange(10**6):
    f('a')

t1 = time()
print 'Function call sec', t1-t0, 'us 100%'

for i in xrange(10**6):
    curry(f, 'a')()

t2 = time()
print 'With Curry', t2-t1, 'us', (t2-t1)/(t1-t0)*100, '%'

def f(a):
    yield
    b = a

for i in xrange(10**6):
    f('a').next()

t3 = time()
print 'With Generator', t3-t2, 'us', (t3-t2)/(t1-t0)*100, '%'

class f:
    def __init__(self, a):
        self.a = a
    def __call__(self):
        b = self.a

for i in xrange(10**6):
    f('a')()

t4 = time()
print 'With Class', t4-t3, 'us', (t4-t3)/(t1-t0)*100, '%'