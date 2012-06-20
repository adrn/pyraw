""" TODO:
    - Fix url: link to github package
"""

from distutils.core import setup, Extension
from distutils.command.build import build
import subprocess

class my_build(build):
    def run(self):
        subprocess.Popen(["gcc","-o","pyraw/dcraw", "-O4","src/dcraw.c", "-lm", "-DNODEPS"]).communicate()[0]
        build.run(self)

setup(name='PyRaw',
      version='0.0',
      description='Python Raw Image Package',
      author='Adrian Price-Whelan',
      author_email='adrn@astro.columbia.edu',
      url='http://www.github.com/link/here',
      packages=['pyraw'],
      package_data={'pyraw': ['dcraw']},
      cmdclass={"build":my_build},
      requires=['Numpy (>=1.4)', 'Pyfits (>=3.0)'],
     )