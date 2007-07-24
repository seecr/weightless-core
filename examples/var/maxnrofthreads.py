import thread, time

def t(parm1,parm2):
	time.sleep( 1000 )

tc = 0
try:
	while 1:
		thread.start_new_thread( t, (None,None) )
		tc += 1
		time.sleep( 0.001 )
finally:
	print tc