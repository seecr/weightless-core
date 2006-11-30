#!/bin/bash

mydir=$(cd $(dirname $0); pwd)
installdir=$(cd $mydir/..; pwd)

source $mydir/functions.sh

isroot

rm -rf /tmp/install_sendfile
mkdir /tmp/install_sendfile
cd /tmp/install_sendfile
wget -q http://download.cq2.org/third-party/py-sendfile-1.2.1.tar.bz2
tar xjf py-sendfile-1.2.1.tar.bz2
cd py-sendfile-1.2.1
python setup.py install --install-lib=$installdir
echo "*
* Finished: Installing sendfile"
