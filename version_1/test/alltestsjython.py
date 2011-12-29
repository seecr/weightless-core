print "importing setDefaultEncoding"
from org.python.core.codecs import setDefaultEncoding
print "setting defaul encoding"
setDefaultEncoding('utf-8')
print "importing sys.path"
from sys import path
print "setting path"
path.insert(0, "..")
print "importing Weightless"
import weightless
print "importing ComposePyTest"
from core.composetest import ComposePyTest
print "importing main"
from unittest import main
print "exec main"
main()
