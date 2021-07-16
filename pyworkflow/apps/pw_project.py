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

from pyworkflow import Config
from pyworkflow.project import Manager
from pyworkflow.gui.project import ProjectWindow
import pyworkflow.utils as pwutils

import logging
logger = logging.getLogger(__name__)

def openProject(projectName):
    """ Opens a scipion project:

    :param projectName: Name of a existing project to open,
            or "here" to create a project in the current working dir,
            or "last" to open the most recent project

    """
    manager = Manager()
    projName = os.path.basename(projectName)

    # Handle special name 'here' to create a project
    # from the current directory
    if projName == 'here':
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

    elif projName == 'last':  # Get last project
        projects = manager.listProjects()
        if not projects:
            sys.exit("No projects yet, cannot open the last one.")
        projName = projects[0].projName

    projPath = manager.getProjectPath(projName)

    if os.path.exists(projPath):
        projWindow = ProjectWindow(projPath)
        projWindow.show()
    else:
        logger.error("Can't open project %s. It does not exist" % projPath)

if __name__ == '__main__':

    if len(sys.argv) > 1:
        openProject(sys.argv[1])
    else:
        logger.info("usage: pw_project.py PROJECT_NAME or here or last")
