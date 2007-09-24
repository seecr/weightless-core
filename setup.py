## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2007 Seek You Too B.V. (CQ2) http://www.cq2.nl
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

if python_version() >= '2.5':
    setup(
        name='weightless',
        packages=['weightless', 'weightless.http', 'weightless.utils'],
        ext_modules=[Extension("weightless.python2_5._compose_pyx", ["weightless/python2_5/_compose_pyx.pyx"])],
        cmdclass = {'build_ext': build_ext}
)

else:
    setup(
        name='weightless',
        packages=['weightless', 'weightless.http']
)

