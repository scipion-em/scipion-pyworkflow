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
This module is responsible for launching protocol executions.
"""
import sys
from pyworkflow.utils import LoggingConfigurator

if __name__ == '__main__':

    if len(sys.argv) == 6:
        projPath = sys.argv[1]
        dbPath = sys.argv[2]
        protId = int(sys.argv[3])
        stdOut = sys.argv[4]
        stdErr = sys.argv[5]

        LoggingConfigurator.setUpProtocolRunLogging(stdOut, stdErr)

        from pyworkflow.protocol import runProtocolMain
        runProtocolMain(projPath, dbPath, protId)
        
    else:
        from os.path import basename
        print("usage: %s projPath dbPath protocolID pathToStdoutLog pathToStdErrLog." % basename(sys.argv[0]))
        print("sys.argv: %s" % sys.argv)
        sys.exit(1)
