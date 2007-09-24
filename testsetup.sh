set -e

rm -rf tmp build

pyversion=2.4

PYTHONPATH=`pwd`/deps.d/Pyrex-0.9.5.1a python$pyversion setup.py install --root tmp

(
cd test
PYTHONPATH=`pwd`/../tmp/usr/lib/python$pyversion/site-packages python$pyversion alltests.py
)

rm -rf tmp build
