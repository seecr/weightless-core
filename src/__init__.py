from platform import python_version

#from _compose_py import compose, RETURN
#from _pool import Pool
#from _socket import Socket
#from _select import Select
#from _service import Service
#from _template import Template

#python 2.4 stuff
from _acceptor import Acceptor
from _reactor import Reactor
from _httpreader import HttpReader
from _httpserver import HttpServer

if python_version() >= "2.5":
    from _compose_pyx import compose, RETURN
