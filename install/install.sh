#!/bin/bash

basedir=$(cd `dirname $0`; pwd)

source $basedir/functions.sh

aptitude install python2.5
echo "*
* We will now make python 2.5 the default python version."
cd /usr/bin
rm python
ln -s python2.5 python
aptitude_install http://debian.cq2.org stable main python-sendfile

if [ -z "$(which easy_install-2.5)" ]; then
  cd /tmp
  wget http://peak.telecommunity.com/dist/ez_setup.py
  python ez_setup.py
  rm ez_setup.py
fi
easy_install-2.5 Pyrex==0.9.5.1a
