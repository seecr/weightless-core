set -e

rm -rf tmp build

PYTHONPATH=`pwd`/deps.d/Pyrex-0.9.5.1a python2.5 setup.py install --root tmp

PYTHONPATH=`pwd`/tmp/usr/lib/python2.5/site-packages cd test; python2.5 alltests.py

rm -rf tmp build