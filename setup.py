from distutils.core import setup, Extension
from distutils.command.build import build
import subprocess

__author__ = "adrn"

class my_build(build):
    def run(self):
        subprocess.Popen(["gcc","-o","pyraw/dcraw", "-O4","src/dcraw.c", "-lm", "-DNODEPS"]).communicate()[0]
        build.run(self)

setup(name='pyraw',
      version='0.1',
      description='Python Raw Image Package',
      author='Adrian Price-Whelan',
      author_email='adrn@astro.columbia.edu',
      url='https://www.github.com/adrn/pyraw',
      packages=['pyraw'],
      package_data={'pyraw': ['dcraw']},
      cmdclass={"build":my_build},
      requires=['Numpy (>=1.4)', 'Pyfits (>=3.0)'],
     )