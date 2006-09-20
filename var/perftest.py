#!/usr/bin/python

import wlfile
import select
import tempfile
import os
import hotshot, hotshot.stats, test.pystone

f = tempfile.NamedTemporaryFile()
try:
	for line in ('%08d' % n for n in xrange(513)):
		f.write(line)
	f.seek(0)

	def main():
		for n in range(1000):
			wlf = wlfile.WlFileReader(f.name)
			r, w, e = select.select([wlf], [], [], 1.0)
			data = wlf.recv('ignore this')
			r, w, e = select.select([wlf], [], [], 1.0)
			data = wlf.recv()

	prof = hotshot.Profile("stones.prof")
	prof.runcall(main)
	prof.close()
	os.system('python hotshot2kcachegrind.py -o cachegrind.out stones.prof; kcachegrind cachegrind.out')

finally:
	f.close()

