from Queue import Queue, Empty
from threading import Thread
from time import sleep
from types import GeneratorType

_NUMBER_OF_WORKERS = 10
_commands = Queue()

def _worker():
	while True:
		cmd = _commands.get()
		if cmd == 'stop': return
		list(cmd)

_pool = [Thread(None, _worker) for i in range(_NUMBER_OF_WORKERS)]
map(lambda thread: thread.setDaemon(True), _pool)
map(Thread.start, _pool)

""" Interface """

yield_cpu = lambda: sleep(0.00001)

def shutdown():
	for t in pool: _commands.put('stop')
	map(Thread.join, pool)

def execute(generator):
	if not type(generator) == GeneratorType:
		raise TypeError('execute() expects a generator')
	_commands.put(generator)
	yield_cpu()