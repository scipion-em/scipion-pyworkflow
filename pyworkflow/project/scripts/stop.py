#!/usr/bin/env python
# **************************************************************************
# *
# * Authors:     Yaiza Rancel (yrancel@cnb.csic.es)
# *
# * Unidad de Bioinformatica of Centro Nacional de Biotecnologia, CSIC
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

import pyworkflow as pw
import pyworkflow.utils as pwutils
from pyworkflow.project import Manager, Project


def usage(error):
    print("""
    ERROR: %s

    Usage: scipion python -m pyworkflow.project.scripts.stop project_name
        This script will stop all running protocols of the specified project.
    """ % error)
    sys.exit(1)


n = len(sys.argv)

if n > 2:
    usage("This script accepts 1 mandatory parameter: the project name")

projName = sys.argv[1]

path = pw.join('gui', 'no-tkinter')
sys.path.insert(1, path)

manager = Manager()

if not manager.hasProject(projName):
    usage("There is no project with this name: %s"
          % pwutils.red(projName))

# the project may be a soft link which may be unavailable to the cluster so get the real path
try:
    projectPath = os.readlink(manager.getProjectPath(projName))
except:
    projectPath = manager.getProjectPath(projName)

project = Project(pw.Config.getDomain(), projectPath)
project.load()

runs = project.getRuns()

# Now assuming that there is no dependencies between runs
# and the graph is linear
for prot in runs:
    if prot.isActive():
        try:
            project.stopProtocol(prot)
        except:
            print("Couldn't stop protocol %s" % prot)
