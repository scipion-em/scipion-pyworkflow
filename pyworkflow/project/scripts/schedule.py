# **************************************************************************
# *
# * Authors:     Pablo Conesa (pconesa@cnb.csic.es)
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
import time

import pyworkflow as pw
from pyworkflow.project import Manager
from pyworkflow.project import Project
import pyworkflow.utils as pwutils
from pyworkflow.protocol import INITIAL_SLEEP_TIME


def usage(error):
    print("""
    ERROR: %s
    
    Usage: python -m pyworkflow.project.scripts.schedule projectName 
    
              options: --ignore ProtClassName1 ProtClassName2 ProtClassLabel1 ...
              
        This script will schedule all the protocols in a project. If '--ignore' 
          options is passed, it doesn't schedule those protocols that belongs to 
          ProtClassName1 or ProtClassName2 class, also those protocols with a 
          objLabel equals to ProtClassLabel1
    """ % error)
    sys.exit(1)


n = len(sys.argv)

if n < 2:
    usage("This script accepts 1 mandatory parameter: the project name.")
elif n > 2 and sys.argv[2] != '--ignore':
    usage("The protocol class names to be ignored must be after a '--ignore' flag.")

projName = sys.argv[1]

# This fails, since it is triggering matplotlib.pyplot and then import error happens:
# ... pyworkflow/gui/no-tkinter/_tkinter.py: invalid ELF header. If we want this back we might need to
# invest some time "faking" tkinter again for python3.
# path = pw.join('gui', 'no-tkinter')
# sys.path.insert(1, path)

# Create a new project
manager = Manager()

if not manager.hasProject(projName):
    usage("There is no project with this name: %s"
          % pwutils.red(projName))

# the project may be a soft link which may be unavailable to the cluster
# so get the real path

try:
    projectPath = os.readlink(manager.getProjectPath(projName))
except:
    projectPath = manager.getProjectPath(projName)

project = Project(pw.Config.getDomain(), projectPath)
project.load()

runGraph = project.getRunsGraph()
roots = runGraph.getRootNodes()

# Now assuming that there is no dependencies between runs
# and the graph is lineal

for root in roots:
    for child in root.getChilds():
        workflow, _ = project._getWorkflowFromProtocol(child.run)
        for prot, level in workflow.values():
            protClassName = prot.getClassName()
            protLabelName = prot.getObjLabel()
            if (protClassName not in sys.argv[3:] and
                    protLabelName not in sys.argv[3:]):
                project.scheduleProtocol(prot,
                                         initialSleepTime=level*INITIAL_SLEEP_TIME)
            else:
                print(pwutils.blueStr("\nNot scheduling '%s' protocol named '%s'.\n"
                                      % (protClassName, protLabelName)))
