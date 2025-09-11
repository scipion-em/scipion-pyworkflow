#!/usr/bin/env python
# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es)
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 3 of the License, or
# * (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
# * 02111-1307  USA
# *
# *  All comments concerning this program package may be sent to the
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************
"""
Launch main project window 
"""

import sys
import os
from subprocess import Popen

from pyworkflow import Config, PYTHON
from pyworkflow.project import Manager
from pyworkflow.gui.project import ProjectWindow
import pyworkflow.utils as pwutils

HERE = 'here'
LAST = 'last'
LIST = 'list'

def openProject(projectName):
    """ Opens a scipion project:

    :param projectName: Name of an existing project to open,
            or "here" to create a project in the current working dir,
            or "last" to open the most recent project

    """
    manager = Manager()
    projName = os.path.basename(projectName)


    if projName == LIST:
        showProjectList(manager)
        return
    # Handle special name 'here' to create a project
    # from the current directory
    elif projName == HERE:
        cwd = Config.SCIPION_CWD

        if " " in cwd:
            print("Projects can't have spaces in the name: %s" % cwd)
            sys.exit(1)

        print("\nYou are trying to create a project here:",
              pwutils.cyan(cwd))

        if os.listdir(cwd):
            print(pwutils.red('\nWARNING: this folder is not empty!!!'))
        key = input("\nDo you want to create a project here? [y/N]?")

        if key.lower().strip() != 'y':
            print("\nAborting...")
            sys.exit(0)
        else:
            print("\nCreating project....")
            projName = os.path.basename(cwd)
            projDir = os.path.dirname(cwd)
            manager.createProject(projName, location=projDir)

    elif projName == LAST:  # Get last project
        projects = manager.listProjects()
        if not projects:
            sys.exit("No projects yet, cannot open the last one.")
        projName = projects[0].projName

    projPath = manager.getProjectPath(projName)

    if os.path.exists(projPath):

        # This opens the project in the same process as the launcher. This is good for directly debugging code
        # but  does not allow -O or not execution (usage of __debug__ flag).
        # All we can do is to go straight to loading the project if debug is active or running optimized.
        if Config.debugOn() or not __debug__:


            # This may or may not be run Optimized (-O). It depends on the call to scipion last (launcher)
            print("Launching project in debug or optimized...")
            projWindow = ProjectWindow(projPath)
            projWindow.show()
        else:

            # Run this same  script optimized: Defined in scipion module under scipion-app: Circular definition. To fix! Bad design.
            print("Launching project optimized...")
            Popen([PYTHON, "-O", "-m","scipion", "project", projectName])


    else:
        print("Can't open project %s. It does not exist" % projPath)

        # Show the list of projects
        showProjectList(manager)

def showProjectList(manager):

    projects = manager.listProjects()

    print("\n******** LIST OF PROJECTS *******\n")
    for project in projects:
        print(project.projName)
    print("\n")
if __name__ == '__main__':

    if len(sys.argv) > 1:
        openProject(sys.argv[1])
    else:
        print("usage: pw_project.py PROJECT_NAME or %s or %s or %s" % (HERE, LAST, LIST))
