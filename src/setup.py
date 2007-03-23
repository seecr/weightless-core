from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext

setup(name='wlcompose', ext_modules=[Extension("wlcompose", ["wlcompose.pyx"])],
        cmdclass = {'build_ext': build_ext}
)
