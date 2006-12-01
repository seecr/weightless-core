from distutils.core import setup

setup (name = 'weightless',
	version = '0.1',
	description = 'Lightweight server framework',
	package_dir = { 'weightless' : '.' },
	packages = ['weightless', 'weightless.wlsocket', 'weightless.wlthread'])
