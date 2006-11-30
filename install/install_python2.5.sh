#!/bin/bash

mydir=$(cd $(dirname $0); pwd)

source $mydir/functions.sh

isroot

if [ "2.5" != $(python -c "import sys; print sys.version[:3]") ]; then
	echo "*
* Installing python version 2.5"
	
	rm -rf /tmp/install_python_2.5
	mkdir /tmp/install_python_2.5
	cd /tmp/install_python_2.5
	wget -q http://download.cq2.org/third-party/Python-2.5.tar.bz2
	tar xjf Python-2.5.tar.bz2
	cd Python-2.5
	./configure
	make
	make install
	rm -rf /tmp/install_python_2.5
	echo "*
* Finished: Installing python version 2.5"
fi
