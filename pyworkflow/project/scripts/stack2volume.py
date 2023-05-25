#!/usr/bin/env python


import sys
from glob import glob

from pwem.convert import Ccp4Header
import pyworkflow.utils as pwutils


def usage(error):
    print("""
    ERROR: %s
    
    Usage: scipion python -m pyworkflow.project.scripts.stack2volume PATH
        PATH: path to look for stack files
    The script will swap the dimensions in the header of a stack to make them 
    volumes. Something like 10 x 1 x 10 x 10 will be changed to 1 x 10 x 10 x 10
    """ % error)
    sys.exit(1)    


if len(sys.argv) != 2:
    usage("Incorrect number of input parameters")

path = sys.argv[1]

print("Looking for files like: %s" % path)


for file in glob(path):

    print("Changing header of %s" % file)
    try:
        header = Ccp4Header(file, readHeader=True)
        # Flag it as volume.
        header.setISPG(401)
        header.writeHeader()

    except Exception as e:
        print(pwutils.red("Failed to change header: % s" % e))
