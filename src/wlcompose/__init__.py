from os import system
from os.path import dirname, isfile, join, getmtime

mydir = dirname(__file__)
solib = join(mydir, 'compose.so')
pyxsource = join(mydir, 'compose.pyx')

if not isfile(solib):
	print '* Extension compose.so not found,'
	if isfile(pyxsource):
		print '* but PyRex source found, assuming development environment'
		print '* Now compiling compose.so extension.'
		system("cd %s; python2.5 setup.py build_ext --inplace" % mydir)
	else:
		print '* and no PyRex source found.  Your installation is broken.'
		raise ImportError('no compose.so and no compose.pyx either.')
else:
	if isfile(pyxsource) and getmtime(solib) < getmtime(pyxsource):
		print '* Extension compose.so found, but newer Pyrex source also found.'
		print '* Recompiling compose extension'
		system("cd %s; python2.5 setup.py build_ext --inplace" % mydir)

from compose import compose, RETURN

