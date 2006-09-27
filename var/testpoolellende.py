

from wlselect import WlSelect
from wlthreadpool import execute

def job():
	yield None
	print 'job'

b = WlSelect()
execute(job()).wait()
b = WlSelect()
execute(job()).wait()
c = WlSelect()
execute(job()).wait()
d = WlSelect()
execute(job()).wait()
e = WlSelect()
execute(job()).wait()
f = WlSelect()
execute(job()).wait()
g = WlSelect()
execute(job()).wait()
h = WlSelect()
execute(job()).wait()
i = WlSelect()
execute(job()).wait()
j = WlSelect()
execute(job()).wait()

