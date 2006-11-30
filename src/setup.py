from distutils.core import setup

setup (name = 'weightless',
	version = '0.1',
	description = 'Lightweight server framework',
	package_dir = { 'weightless' : 'src' },
	packages = ['weightless', 'weightless.wlsocket', 'weightless.wlthread'])
