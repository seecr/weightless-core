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


