from os import system
from os.path import dirname, isfile, join, getmtime

mydir = dirname(__file__)
solib = join(mydir, 'compose.so')
pyxsource = join(mydir, 'compose.pyx')

if not isfile(solib) or getmtime(solib) < getmtime(pyxsource):
    print '* Extension compose.so not found or outdated.'
    print '* You are either in a development environment or'
    print '* your installation of weightless is broken. Assuming'
    print '* the former.'
    print '* Now compiling compose.so extension.', mydir
    system("cd %s; python2.5 setup.py build_ext --inplace" % mydir)

from compose import compose, RETURN

