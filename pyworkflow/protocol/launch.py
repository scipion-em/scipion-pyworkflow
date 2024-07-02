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
This module is responsible for launching local protocol executions:

1- Check if the protocol will be submitted to a queue (using Queue template from config)
2- Build the command that will be launched.

"""

import os
import re
import logging
logger = logging.getLogger(__file__)
from subprocess import Popen, PIPE
import pyworkflow as pw
from pyworkflow.exceptions import PyworkflowException
from pyworkflow.utils import (redStr, greenStr, makeFilePath, join, process,
                              getHostFullName)
from pyworkflow.protocol.constants import UNKNOWN_JOBID, STATUS_FAILED, STATUS_FINISHED, STATUS_RUNNING


# ******************************************************************
# *         Public functions provided by the module
# ******************************************************************

def launch(protocol, wait=False, stdin=None, stdout=None, stderr=None):
    """ This function should be used to launch a protocol. """
    _launchLocal(protocol, wait, stdin, stdout, stderr)


def stop(protocol):
    """
    Stop function for three scenarios:
    - If the queue is not used, kill the main protocol process and its child processes.
    - If the queue is used and the entire protocol is sent to the queue, cancel the job running the protocol using
    scancel.
    - If the queue is used and individual steps are sent to the queue, cancel all active jobs and kill the main protocol
    process and its child processes.
    """
    if protocol.useQueue() and not protocol.isScheduled():
        jobIds = protocol.getJobIds()
        for jobId in jobIds: # Iter even though it contains only one jobId
            host = protocol.getHostConfig()
            cancelCmd = host.getCancelCommand() % {'JOB_ID': jobId}
            logger.info(cancelCmd)
            _run(cancelCmd, wait=True)

        if protocol.useQueueForSteps():
            process.killWithChilds(protocol.getPid())
    else:
        process.killWithChilds(protocol.getPid())


def schedule(protocol, initialSleepTime=0, wait=False):
    """ Use this function to schedule protocols that are not ready to
    run yet. Right now it only make sense to schedule jobs locally.
    """
    cmd = '%s %s' % (pw.PYTHON, pw.getScheduleScript())
    cmd += ' "%s" "%s" %s "%s" --initial_sleep %s' % (protocol.getProject().path,
                              protocol.getDbPath(),
                              protocol.strId(),
                              protocol.getScheduleLog(),
                              initialSleepTime)
    pid = _run(cmd, wait)
    protocol.setPid(pid)  # Set correctly the pid


# ******************************************************************
# *         Internal utility functions
# ******************************************************************
def _runsLocally(protocol):
    """ Return True if this protocol is running in this machine,
    where the PID makes sense.
    """
    return protocol.getHostFullName() == getHostFullName()


# ******************************************************************
# *                 Function related to LAUNCH
# ******************************************************************
def _getAppsProgram(prog):
    """ Get a command to launch a program under the apps folder.
    """
    return "%s %s" % (pw.PYTHON, pw.join(pw.APPS, prog))


def _launchLocal(protocol, wait, stdin=None, stdout=None, stderr=None):
    """

    :param protocol: Protocol to launch
    :param wait: Pass true if you want to wait for the process to finish
    :param stdin: stdin object to direct stdin to
    :param stdout: stdout object to send process stdout
    :param stderr: stderr object to send process stderr
    """

    command = '{python} {prot_run} "{project_path}" "{db_path}" {prot_id} "{stdout_log}" "{stderr_log}"'.format(
        python=pw.PYTHON,
        prot_run=pw.join(pw.APPS, 'pw_protocol_run.py'),
        project_path=protocol.getProject().path,
        db_path=protocol.getDbPath(),
        prot_id=protocol.strId(),
        # We make them absolute in case working dir is not passed to the node when running through a queue.
        # The reason is that since 3.0.27, the first thing that is affected by the current working dir is the
        # creation of the logs. Before event than loading the project, which was and is setting the working dir to
        # the project path. IMPORTANT: This assumes the paths before the queue and after the queue (nodes) are the same
        # Which I think is safe since we are passing here "project_path" that is absolute.
        stdout_log=os.path.abspath(protocol.getStdoutLog()),
        stderr_log=os.path.abspath(protocol.getStderrLog())
    )

    hostConfig = protocol.getHostConfig()

    # Clean Pid and JobIds
    protocol.cleanExecutionAttributes()
    protocol._store(protocol._jobId)

    # Handle three use cases: one will use the job ID, and the other two will use the process ID.
    if protocol.useQueueForProtocol():  # Retrieve the job ID and set it; this will be used to control the protocol.
        submitDict = dict(hostConfig.getQueuesDefault())
        submitDict.update(protocol.getSubmitDict())
        submitDict['JOB_COMMAND'] = command
        jobId = _submit(hostConfig, submitDict)
        if jobId is None or jobId == UNKNOWN_JOBID:
            protocol.setStatus(STATUS_FAILED)
        else:
            protocol.setJobId(jobId)
            protocol.setPid(0)  # we go through the queue, so we rely on the jobId
    else:  # If not, retrieve and set the process ID (both for normal execution or when using the queue for steps)
        pId = _run(command, wait, stdin, stdout, stderr)
        protocol.setPid(pId)


def analyzeFormattingTypeError(string, dictionary):
    """ receives a string with %(VARS) to be replaced with a dictionary
     it splits te string by \n and test the formatting per line. Raises an exception if any line fails
     with all problems found"""

    # Do the replacement line by line
    lines = string.split("\n")

    problematicLines = []
    for line in lines:
        try:
            line % dictionary
        except KeyError as e:
            problematicLines.append(line + " --> variable not present in this context.")
        except Exception as e:
            problematicLines.append(line + " --> " + str(e))

    if problematicLines:
        return PyworkflowException('Following lines in %s seems to be problematic.\n'
                                   'Values known in this context are: \n%s'
                                   'Please review its format or content.\n%s' % (dictionary, pw.Config.SCIPION_HOSTS, "\n".join(problematicLines)),
                                   url=pw.DOCSITEURLS.HOST_CONFIG)


def _submit(hostConfig, submitDict, cwd=None, env=None):
    """ Submit a protocol to a queue system. Return its job id.
    """
    # Create first the submission script to be launched
    # formatting using the template
    template = hostConfig.getSubmitTemplate()

    try:
        template = template % submitDict
    except Exception as e:
        # Capture parsing errors
        exception = analyzeFormattingTypeError(template, submitDict)

        if exception:
            raise exception
        else:
            # If there is no exception, then raise actual one
            raise e

    # FIXME: CREATE THE PATH FIRST
    scripPath = submitDict['JOB_SCRIPT']
    f = open(scripPath, 'w')
    # Ensure the path exists
    makeFilePath(scripPath)
    # Add some line ends because in some clusters it fails
    # to submit jobs if the submit script does not have end of line
    f.write(template + '\n\n')
    f.close()
    # This should format the command using a template like: 
    # "qsub %(JOB_SCRIPT)s"
    command = hostConfig.getSubmitCommand() % submitDict
    gcmd = greenStr(command)
    logger.info("** Submitting to queue: '%s'" % gcmd)

    p = Popen(command, shell=True, stdout=PIPE, cwd=cwd, env=env)
    out = p.communicate()[0]
    # Try to parse the result of qsub, searching for a number (jobId)
    # Review this, seems to exclusive to torque batch system
    s = re.search(r'(\d+)', str(out))
    if p.returncode == 0 and s:
        job = int(s.group(0))
        logger.info("Launched job with id %s" % job)
        return job
    else:
        logger.info("Couldn't submit to queue for reason: %s " % redStr(out.decode()))
        return UNKNOWN_JOBID

def _checkJobStatus(hostConfig, jobid):
    """
    General method to verify the job status in the queue based on the jobId and host.conf CHECK_COMMAND
    returns: STATUS_FINISHED (finished) or STATUS_RUNNING (running)
    """
    command = hostConfig.getCheckCommand() % {"JOB_ID": jobid}
    logger.debug("checking job status for %s: %s" % (jobid, command))

    p = Popen(command, shell=True, stdout=PIPE, preexec_fn=os.setsid)

    out = p.communicate()[0].decode(errors='backslashreplace')

    jobDoneRegex = hostConfig.getJobDoneRegex()
    logger.debug("Queue engine replied %s, variable JOB_DONE_REGEX has %s" % (out, jobDoneRegex))
    # If nothing is returned we assume job is no longer in queue and thus finished
    if out == "":
        logger.warning("Empty response from queue system to job (%s)" % jobid)
        return STATUS_FINISHED

    # If some string is returned we use the JOB_DONE_REGEX variable (if present) to infer the status
    elif jobDoneRegex is not None:
        s = re.search(jobDoneRegex, out)
        if s:
            logger.debug("Job (%s) finished" % jobid)
            return STATUS_FINISHED
        else:
            logger.debug("Job (%s) still running" % jobid)
            return STATUS_RUNNING
    # If JOB_DONE_REGEX is not defined and queue has returned something we assume that job is still running
    else:
        return STATUS_RUNNING

def _run(command, wait, stdin=None, stdout=None, stderr=None):
    """ Execute a command in a subprocess and return the pid. """
    gcmd = greenStr(command)
    logger.info("** Running command: '%s'" % gcmd)
    p = Popen(command, shell=True, stdout=stdout, stderr=stderr)
    pid = p.pid
    if wait:
        p.wait()

    return pid
