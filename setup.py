## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2008 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext
from platform import python_version

setupArgs = {
    'name': 'weightless',
    'version': '%VERSION%',
    'url': 'http://www.weightless.io',
    'author': 'Seek You Too',
    'author_email': 'info@cq2.nl',
    'description': 'Weightless is a High Performance Asynchronous Networking Library.',
    'long_description': 'Weightless is a High Performance Asynchronous Networking Library.',
    'license': 'GNU Public License',
    'platforms': 'all'
}

if python_version() >= '2.5':
    setup(
        packages=['weightless', 'weightless.python2_5', 'weightless.http', 'weightless.utils'],
        ext_modules=[Extension("weightless.python2_5._compose_pyx", ["weightless/python2_5/_compose_pyx.pyx"])],
        cmdclass = {'build_ext': build_ext},
        **setupArgs
    )

else:
    setup(
        packages=['weightless', 'weightless.http'],
        **setupArgs
    )

