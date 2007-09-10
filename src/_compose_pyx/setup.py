from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext

setup(name='compose', ext_modules=[Extension("compose", ["compose.pyx"])],
        cmdclass = {'build_ext': build_ext}
)
