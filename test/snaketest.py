from unittest import main
from cq2utils import CQ2TestCase
from imp import load_source
from os import listdir
from os.path import join
from weightless import compose
import sys

class MySimpleModule:
    pass

class Snake(object):
    def __init__(self, basedir):
        self._basedir = basedir
        self._modules = {}
        for f in listdir(self._basedir):
            if f not in self._modules:
                self.loadModule(f)

    def loadModule(self, name):
        basket = {}
        execfile(join(self._basedir, name), {'__builtins__': {'__import__': self.__import__, 'str': str}}, basket)
        self._modules[name] = basket

    def __import__(self, name, globals=None, locals=None, fromlist=None):
        if not name in self._modules:
            if not name in listdir(self._basedir):
                raise KeyError('Error importing ' + name)
            else:
                self.loadModule(name)
        symbols = self._modules[name]
        fakemodule = MySimpleModule()
        fakemodule.__dict__ = self._modules[name]
        globals[name] = fakemodule

    def process(self, path):
        module = self._modules[path]
        locals = {}
        globals = {'page': module['page']}
        exec 'generator = page()' in globals, locals
        return compose(locals['generator'])

class SnakeTest(CQ2TestCase):

    def testSimple(self):
        open(self.tempdir+'/testSimple', 'w').write(
"""
def page(*args, **kwargs):
  for n in ('aap', 'noot', 'mies'):
    yield str(n)
"""
        )
        s = Snake(self.tempdir)
        result = ''.join(s.process('testSimple'))
        self.assertEquals('aapnootmies', result)

    def testIncludeOther(self):
        open(self.tempdir+'/simple', 'w').write(
"""
def page(*args, **kwargs):
    yield 'is'
    yield 'snake'
"""
        )
        open(self.tempdir+'/other', 'w').write(
"""
import simple
def page(*args, **kwargs):
    yield 'me'
    yield simple.page()
"""
        )
        s = Snake(self.tempdir)
        result = ''.join(s.process('other'))
        self.assertEquals('meissnake', result)

