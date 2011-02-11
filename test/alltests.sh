#!/bin/bash
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2011 Seek You Too (CQ2) http://www.cq2.nl
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

export LANG=en_US.UTF-8
export PYTHONPATH=.:"$PYTHONPATH"
option=$1                                                  #DO_NOT_DISTRIBUTE
if [ "$option" == "--python" ]; then                       #DO_NOT_DISTRIBUTE
    shift                                                  #DO_NOT_DISTRIBUTE
WEIGHTLESS_COMPOSE_TEST=PYTHON python2.5 _alltests.py "$@" #DO_NOT_DISTRIBUTE
elif [ "$option" == "--c" ]; then                          #DO_NOT_DISTRIBUTE
    shift                                                  #DO_NOT_DISTRIBUTE
python2.5 _alltests.py "$@"                                #DO_NOT_DISTRIBUTE
else                                                       #DO_NOT_DISTRIBUTE
WEIGHTLESS_COMPOSE_TEST=PYTHON python2.5 _alltests.py "$@" #DO_NOT_DISTRIBUTE
python2.5 _alltests.py "$@"
fi                                                         #DO_NOT_DISTRIBUTE
