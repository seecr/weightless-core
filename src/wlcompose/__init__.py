import sys
sys.argv = ['setup.py', 'build_ext', '--inplace']

from os.path import dirname
from os import chdir
selfDir = dirname(__file__)
chdir(selfDir)
execfile('setup.py')

from compose import compose, RETURN
