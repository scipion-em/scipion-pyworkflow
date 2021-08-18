# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es)
# *              Laura del Cano         (ldelcano@cnb.csic.es)
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
This module handles process execution
"""

import sys
from subprocess import check_call
import psutil

from .utils import greenStr
from pyworkflow import Config


# The job should be launched from the working directory!
def runJob(log, programname, params,           
           numberOfMpi=1, numberOfThreads=1, 
           hostConfig=None, env=None, cwd=None, gpuList=None):

    command = buildRunCommand(programname, params, numberOfMpi, hostConfig,
                              env, gpuList=gpuList)
    
    if log is None:
        print("** Running command: %s" % greenStr(command))
    else:
        log.info(greenStr(command))

    return runCommand(command, env, cwd)
        

def runCommand(command, env=None, cwd=None):
    """ Execute command with given environment env and directory cwd """

    # First let us create core dumps if in debug mode
    if Config.debugOn(env):
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,
                           (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        # This is like "ulimit -u 99999999", so we can create core dumps

    # TODO: maybe have to set PBS_NODEFILE in case it is used by "command"
    # (useful for example with gnu parallel)
    check_call(command, shell=True, stdout=sys.stdout, stderr=sys.stderr,
               env=env, cwd=cwd)
    # It would be nice to avoid shell=True and calling buildRunCommand()...

    
def buildRunCommand(programname, params, numberOfMpi, hostConfig=None,
                    env=None, gpuList=None):
    """ Return a string with the command line to run """

    # Convert our list of params to a string, with each element escaped
    # with "" in case there are spaces.
    if not isinstance(params, str):
        params = ' '.join('"%s"' % p for p in params)

    if gpuList:
        params = params % {'GPU': ' '.join(str(g) for g in gpuList)}

    prepend = '' if env is None else env.getPrepend()

    if numberOfMpi <= 1:
        return '%s %s %s' % (prepend, programname, params)
    else:
        assert hostConfig is not None, 'hostConfig needed to launch MPI processes.'

        if programname.startswith('xmipp') and not programname.startswith('xmipp_mpi'):
            programname = programname.replace('xmipp', 'xmipp_mpi')
            
        mpiFlags = '' if env is None else env.get('SCIPION_MPI_FLAGS', '') 

        mpiCmd = hostConfig.mpiCommand.get() % {
            'JOB_NODES': numberOfMpi,
            'COMMAND': "%s `which %s` %s" % (mpiFlags, programname, params),
        }
        return '%s %s' % (prepend, mpiCmd)


def killWithChilds(pid):
    """ Kill the process with given pid and all children processes.
    Params:
     pid: the process id to terminate
    """
    proc = psutil.Process(pid)
    for c in proc.children(recursive=True):
        if c.pid is not None:
            print("Terminating child pid: %d" % c.pid)
            c.kill()
    print("Terminating process pid: %s" % pid)
    if pid is None:
        print("WARNING! Got None PID!!!")
    else:
        proc.kill()


def isProcessAlive(pid):
    try:
        psutil.Process(pid)
        return True
    except Exception:
        return False
