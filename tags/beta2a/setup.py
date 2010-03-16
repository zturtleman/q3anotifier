from distutils.core import setup
import py2exe
import sys

sys.argv.append("py2exe")

setup(windows=['q3anotifier.py'], options = {"py2exe": {"bundle_files": 2, "optimize":2,"compressed":True}}, zipfile="q3anotifier.bin")
