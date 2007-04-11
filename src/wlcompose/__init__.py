from os import system
from os.path import dirname

system("cd %s; python2.5 setup.py build_ext --inplace" % dirname(__file__))

from compose import compose, RETURN
