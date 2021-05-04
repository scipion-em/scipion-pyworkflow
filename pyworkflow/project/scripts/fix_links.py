#!/usr/bin/env python

import sys
import os

from pyworkflow.project import Manager
import pyworkflow.utils as pwutils


def usage(error):
    print("""
    ERROR: %s
    
    Usage: python -m pyworkflow.project.script.fix_links PROJECT SEARCH_DIR
        PROJECT: provide the project name to fix broken links in the imports.
        SEARCH_DIR: provide a directory where to look for the files.
        and fix the links.    
    """ % error)
    os._exit(1)

def main():
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

if __name__ == '__main__':
    main()
