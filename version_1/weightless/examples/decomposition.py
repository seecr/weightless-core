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
