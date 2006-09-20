

print '==========>'
dir(globals())
print '<=========>'
dir(globals()['__builtins__'])
print '<=========='
globals()['__builtins__']['aap'] = 'aap'
print aap

import builtintest3