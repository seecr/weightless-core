from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext

setup(
    name='weightless',
    packages=['weightless', 'weightless.wlcompose', 'weightless.wlhttp', 'weightless.wlsocket', 'weightless.wlthread'],
    ext_modules=[Extension("weightless.wlcompose.compose", ["src/wlcompose/compose.pyx"])],
    cmdclass = {'build_ext': build_ext}
)
