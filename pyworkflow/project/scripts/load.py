#!/usr/bin/env python
# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (delarosatrevin@scilifelab.se) [1]
# *
# * [1] SciLifeLab, Stockholm University
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


import sys
import os
from datetime import datetime

import pyworkflow as pw
import pyworkflow.utils as pwutils
from pyworkflow.project import Manager
from pyworkflow.gui.project import ProjectWindow


def usage(error):
    print("""
    ERROR: %s
    
    Usage: scipion python -m pyworkflow.project.scripts.load /path/to/project
        This script allows to quickly load a project folder without
        importing that in the general user data folder
    """ % error)
    sys.exit(1)    


n = len(sys.argv)

if n < 2 or n > 3:
    usage("Incorrect number of input parameters")
    
pathToProj = os.path.abspath(sys.argv[1])

now = datetime.now()
tempSpace = "loading-%s" % now.strftime('%Y%m%d-%H%M%S')
customUserData = os.path.join(pw.Config.SCIPION_USER_DATA, 'tmp', tempSpace)

projectsDir = os.path.join(customUserData, 'projects')
pwutils.makePath(projectsDir)

print("Loading projects from:\n", projectsDir)

projName = os.path.basename(pathToProj)
pwutils.createAbsLink(pathToProj, os.path.join(projectsDir, projName))
 
# Create a new project
manager = Manager(workspace=customUserData)

proj = manager.loadProject(projName)
projPath = manager.getProjectPath(projName)


class EditorProjectWindow(ProjectWindow):
    def close(self, e=None):
        try:
            print("Deleting temporary folder: ", customUserData)
            pwutils.cleanPath(customUserData)
        except Exception as ex:
            print("Error: ", ex)
        ProjectWindow.close(self, e)


projWindow = EditorProjectWindow(projPath)
projWindow.show()
