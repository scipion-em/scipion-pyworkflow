#!/usr/bin/env python

import sys
import os
import logging

from pyworkflow.config import Config
from pyworkflow.project import Manager
import pyworkflow.utils as pwutils


logging.basicConfig(level=Config.SCIPION_LOG_LEVEL, format=Config.SCIPION_LOG_FORMAT)


def usage(error):
    print("""
    ERROR: %s
    
    Usage: scipion python -m pyworkflow.project.scripts.fix_links PROJECT SEARCH_DIR
        PROJECT: provide the project name to fix broken links in the imports
        SEARCH_DIR: provide a directory where to look for the files and fix the links    
    """ % error)
    sys.exit(1)


if len(sys.argv) != 3:
    usage("Incorrect number of input parameters")

projName = sys.argv[1]
searchDir = os.path.abspath(sys.argv[2])

# Create a new project
manager = Manager()

if not manager.hasProject(projName):
    usage("Nonexistent project: %s" % pwutils.red(projName))

if not os.path.exists(searchDir):
    usage("Nonexistent SEARCH_DIR: %s" % pwutils.red(searchDir))

project = manager.loadProject(projName)
project.fixLinks(searchDir)
