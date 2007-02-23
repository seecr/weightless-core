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