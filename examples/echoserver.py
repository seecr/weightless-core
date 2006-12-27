import sys
from weightless.wlservice import WlService

HOST = 'localhost'

ear = None
service = None

def handler():
  """endlessly read and echo back to the client"""
  while 1:
    received = yield None
    yield "ECHO: %s" % received


if __name__ == '__main__':
  if len(sys.argv) < 2:
    print "Specify port"
    sys.exit(1)
    
  port = int(sys.argv[1])

  service = WlService()
  ear = service.listen(HOST, port, handler)
  raw_input("Server at port %s, Any key to quit" % port)
  ear and ear.close()
  service and service.stop()  
