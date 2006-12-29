import sys
from weightless.wlservice import WlService

def main(sinkFactory):
	args = sys.argv[1:]
	if len(args) < 1:
		print "Specify port"
		sys.exit(1)
	
	HOST = 'localhost'
	
	ear = None
	service = None
	
	port = int(sys.argv[1])
	
	service = WlService()
	ear = service.listen(HOST, port, sinkFactory)
	raw_input("Server at port %s, Any key to quit" % port)
	ear and ear.close()
	service and service.stop()  
