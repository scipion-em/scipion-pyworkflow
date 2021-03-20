# **************************************************************************
# *
# * Authors: Pablo Conesa (pconesa@cnb.csic.es) [1]
# * Authors: Grigory Sharov (gsharov@mrc-lmb.cam.ac.uk) [2]
# *
# * [1] Unidad de Bioinformatica of Centro Nacional de Biotecnologia, CSIC
# * [2] MRC Laboratory of Molecular Biology, MRC-LMB
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 3 of the License, or
# * (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
# * 02111-1307 USA
# *
# * All comments concerning this program package may be sent to the
# * e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************

import sys
import os
import re
from glob import glob

from pyworkflow import Config
from pyworkflow.project import Manager, Project
import pyworkflow.utils as pwutils


if len(sys.argv) != 2:
    print("\tUsage: scipion python %s projectName" %
          os.path.basename(__file__))
    exit(1)

projName = sys.argv[1]
manager = Manager()
if not manager.hasProject(projName):
    print("Project %s not found." % pwutils.red(projName))
    exit(1)

# the project may be a soft link so get the real path
try:
    projectPath = os.readlink(manager.getProjectPath(projName))
except:
    projectPath = manager.getProjectPath(projName)

project = Project(Config.getDomain(), projectPath)
project.load()
prjPath = project.getPath()
print("Project path: ", prjPath)
runs = project.getRuns()

os.makedirs(os.path.join(prjPath, "Trash"), exist_ok=True)

# make a dict with finished Relion protocols
protDict = dict()
for prot in runs:
    protCls = prot.getClassName()
    if prot.getStatus() == "finished" and protCls.startswith("ProtRelion"):
        extraDir = prot._getExtraPath()
        if protCls not in protDict:
            protDict[protCls] = [extraDir]
        else:
            protDict[protCls].append(extraDir)

fnsTemplate = {
    'ProtRelionMotionCor': ['*corrected_micrographs.star', '*.log', '*.TXT'],
    'ProtRelionExtractParticles': ['../micrographs_*.star'],
    'ProtRelionBayesianPolishing': ['*_FCC_cc.mrc', '*_FCC_w0.mrc', '*_FCC_w1.mrc'],
    'ProtRelionPostProcess': ['*masked.mrc'],
    'ProtRelionCtfRefinement': ['*_wAcc_optics-group*.mrc',
                                '*_xyAcc_optics-group*.mrc',
                                '*_aberr-Axx_optics-group_*.mrc',
                                '*_aberr-Axx_optics-group_*.mrc',
                                '*_aberr-Axy_optics-group_*.mrc',
                                '*_aberr-Ayy_optics-group_*.mrc',
                                '*_aberr-bx_optics-group_*.mrc',
                                '*_aberr-by_optics-group_*.mrc',
                                '*_mag_optics-group_*.mrc',
                                '*_fit.star', '*_fit.eps'],
}

baseProts = ['ProtRelionClassify2D', 'ProtRelionClassify3D',
             'ProtRelionRefine3D', 'ProtRelionInitialModel',
             'ProtRelionMultiBody']

moveDict = {}
for prot in protDict:
    if prot in fnsTemplate:
        for protDir in protDict[prot]:
            for regex in fnsTemplate[prot]:
                moveDict[os.path.join(prjPath, protDir, regex)] = os.path.join(prjPath, "Trash", protDir)
    elif prot in baseProts:
        for protDir in protDict[prot]:
            files = sorted(glob(os.path.join(prjPath, protDir, "relion_?t???_*")))
            # Move all files except for the last iteration
            # print(files)
            result = None
            if files:
                s = re.search("_?t(\d{3})_", files[-1])
                if s:
                    result = "relion_[ic]t%03d_" % int(s.group(1))  # group 1 is 3 digits iteration number
                    # print("I'll keep iter %s from %s" % (result, protDir))
            if result:
                for f in files:
                    match = re.search(result, f)
                    if not match:
                        moveDict[os.path.join(prjPath, protDir, f)] = os.path.join(prjPath, "Trash", protDir)

print("Running gentle clean for finished Relion protocols..")
for k, v in moveDict.items():
    try:
        os.makedirs(v, exist_ok=True)
        os.system("mv %s %s 2> /dev/null" % (k, v))
    except:
        pass
print("Done! Files moved to: %s" % pwutils.red(os.path.join(prjPath, "Trash")))
