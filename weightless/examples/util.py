from _compose import compose as compose_raw

""" some decorators for dealing with generators"""

def compose(generator):
    def helper(*args, **kwargs):
        return compose_raw(generator(*args, **kwargs))
    return helper

def autostart(generator):
    def helper(*args, **kwargs):
        g = generator(*args, **kwargs)
        g.next()
        return g
    return helper
