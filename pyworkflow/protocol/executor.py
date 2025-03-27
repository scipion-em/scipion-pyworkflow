# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es)
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia, CSIC
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
This module have the classes for execution of protocol steps.
The basic one will run steps, one by one, after completion.
There is one based on threads to execute steps in parallel
using different threads and the last one with MPI processes.
"""

import logging
logger = logging.getLogger(__name__)
import time
import datetime
import threading
import os

import pyworkflow.utils.process as process
from pyworkflow.utils.path import getParentFolder, removeExt
from pyworkflow.constants import PLUGIN_MODULE_VAR, RUN_JOB_GPU_PARAM_SEARCH
from . import constants as cts

from .launch import _submit, UNKNOWN_JOBID, _checkJobStatus


class StepExecutor:
    """ Run a list of Protocol steps. """
    def __init__(self, hostConfig, **kwargs):
        self.hostConfig = hostConfig
        self.gpuList = kwargs.get(cts.GPU_LIST, None)
        self.protocol = None

    def getGpuList(self):
        """ Return the GPU list assigned to current thread. """
        return self.gpuList

    def setProtocol(self, protocol):
        """ Set protocol to append active jobs to its jobIds. """
        self.protocol = protocol

    def getRunContext(self):
        return {PLUGIN_MODULE_VAR: self.protocol.getPlugin().getName()}

    def runJob(self, log, programName, params,
               numberOfMpi=1, numberOfThreads=1,
               env=None, cwd=None, executable=None):
        """ This function is a wrapper around runJob, 
        providing the host configuration. 
        """
        process.runJob(log, programName, params,
                       numberOfMpi, numberOfThreads,
                       self.hostConfig,
                       env=env, cwd=cwd, gpuList=self._getGPUListForCommand(programName, params), executable=executable, context=self.protocol.getSubmitDict())

    def _getGPUListForCommand(self, program, params):
        """ Returns the list of GPUs if the program or the params have the GPU placeholder %(GPU)s """
        if RUN_JOB_GPU_PARAM_SEARCH in params or RUN_JOB_GPU_PARAM_SEARCH in program:
            return self.getGpuList()
        else:
            return []

    def _getRunnable(self, steps, n=1):
        """ Return the n steps that are 'new' and all its
        dependencies have been finished, or None if none ready.
        """
        rs = []  # return a list of runnable steps

        for s in steps:
            if (s.getStatus() == cts.STATUS_NEW and
                    all(steps[i-1].isFinished() for i in s._prerequisites)):

                if self._isStepRunnable(s):
                    rs.append(s)
                    if len(rs) == n:
                        break
        return rs
    def _isStepRunnable(self, step):
        """ Should be implemented by inherited classes to test extra conditions """
        return True

    def _arePending(self, steps):
        """ Return True if there are pending steps (either running or waiting)
        that can be done and thus enable other steps to be executed.
        """
        return any(s.isRunning() or s.isWaiting() for s in steps)
    
    def runSteps(self, steps, 
                 stepStartedCallback, 
                 stepFinishedCallback,
                 stepsCheckCallback,
                 stepsCheckSecs=3):
        # Even if this will run the steps in a single thread
        # let's follow a similar approach than the parallel one
        # In this way we can take into account the steps graph
        # dependency and also the case when using streaming

        delta = datetime.timedelta(seconds=stepsCheckSecs)
        lastCheck = datetime.datetime.now()

        while True:
            # Get a step to run, if there is any
            runnableSteps = self._getRunnable(steps)

            if runnableSteps:
                step = runnableSteps[0]
                # We found a step to work in, so let's start a new
                # thread to do the job and book it.
                step.setRunning()
                stepStartedCallback(step)
                step.run()
                doContinue = stepFinishedCallback(step)
            
                if not doContinue:
                    break

            elif self._arePending(steps):
                # We have not found any runnable step, but still there
                # there are some running or waiting for dependencies
                # So, let's wait a bit to check if something changes
                time.sleep(0.5)
            else:
                # No steps to run, neither running or waiting
                # So, we are done, either failed or finished :)
                break

            now = datetime.datetime.now()
            if now - lastCheck > delta:
                stepsCheckCallback()
                lastCheck = now

        stepsCheckCallback()  # one last check to finalize stuff


class StepThread(threading.Thread):
    """ Thread to run Steps in parallel. """
    def __init__(self, step, lock):
        threading.Thread.__init__(self)
        self.thId = step.getObjId()
        self.step = step
        self.lock = lock

    def run(self):
        error = None
        try:
            self.step._run()  # not self.step.run() , to avoid race conditions
        except Exception as e:
            error = str(e)
            logger.error("Couldn't run the code in a thread." , exc_info=e)
        finally:
            with self.lock:
                if error is None:
                    self.step.setFinished()
                else:
                    self.step.setFailed(error)


class ThreadStepExecutor(StepExecutor):
    """ Run steps in parallel using threads. """
    def __init__(self, hostConfig, nThreads, **kwargs):
        StepExecutor.__init__(self, hostConfig, **kwargs)
        self.numberOfProcs = nThreads
        # If the gpuList was specified, we need to distribute GPUs among
        # all the threads
        self.gpuDict = {}

        self._assignGPUperNode()

    def _assignGPUperNode(self):
        # If we have GPUs
        if self.gpuList:

            nThreads = self.numberOfProcs

            # Nodes: each concurrent steps
            nodes = range(1, nThreads+1)

            # Number of GPUs
            nGpu = len(self.gpuList)

            # If more GPUs than threads
            if nGpu > nThreads:

                # Get the ratio: 2 GPUs per thread? 3 GPUs per thread?
                # 3 GPU and 2 threads is rounded to 1 (flooring)
                step = int(nGpu / nThreads)
                spare = nGpu % nThreads
                fromPos = 0
                # For each node(concurrent thread)
                for node in nodes:
                    # Store the GPUS per thread:
                    # GPUs: 0 1 2
                    # Threads 2 (step 1)
                    # Node 0 : GPU 0 1
                    # Node 1 : GPU 2

                    extraGpu = 1 if spare>0 else 0
                    toPos = fromPos + step +extraGpu
                    gpusForNode = list(self.gpuList[fromPos:toPos])

                    newGpusForNode = self.cleanVoidGPUs(gpusForNode)
                    if len(newGpusForNode) == 0:
                        logger.info("Gpu slot cancelled: all were null Gpus -> %s" % gpusForNode)
                    else:
                        logger.info("GPUs %s assigned to node %s" % (newGpusForNode, node))
                        self.gpuDict[-node] = newGpusForNode

                    fromPos = toPos
                    spare-=1

            else:
                # Expand gpuList repeating until reach nThreads items
                if nThreads > nGpu:
                    logger.warning("GPUs are no longer extended. If you want all GPUs to match threads repeat as many "
                                   "GPUs as threads.")
                    # newList = self.gpuList * (int(nThreads / nGpu) + 1)
                    # self.gpuList = newList[:nThreads]

                for index, gpu in enumerate(self.gpuList):

                    if gpu == cts.VOID_GPU:
                        logger.info("Void GPU (%s) found in the list. Skipping the slot." % cts.VOID_GPU)
                    else:
                        logger.info("GPU slot for gpu %s." % gpu)
                        # Any negative number in the key means a free gpu slot. can't be 0!
                        self.gpuDict[-index-1] = [gpu]

    def cleanVoidGPUs(self, gpuList):
        newGPUList=[]
        for gpuid in gpuList:
            if gpuid == cts.VOID_GPU:
                logger.info("Void GPU detected in %s" % gpuList)
            else:
                newGPUList.append(gpuid)
        return newGPUList

    def getGpuList(self):
        """ Return the GPU list assigned to current thread
        or empty list if not using GPUs. """

        # If the node id has assigned gpus?
        nodeId = threading.current_thread().thId
        if nodeId in self.gpuDict:
            gpus = self.gpuDict.get(nodeId)
            logger.info("Reusing GPUs (%s) slot for %s" % (gpus, nodeId))
            return gpus
        else:

            gpus = self.getFreeGpuSlot(nodeId)
            if gpus is None:
                logger.warning("Step on node %s is requesting GPUs but there isn't any available. Review configuration of threads/GPUs. Returning an empty list." % nodeId)
                return []
            else:
                return gpus
    def getFreeGpuSlot(self, stepId=None):
        """ Returns a free gpu slot available or None. If node is passed it also reserves it for that node

        :param node: node to make the reserve of Gpus
        """
        for node in self.gpuDict.keys():
            # This is a free node. Book it
            if node < 0:
                gpus = self.gpuDict[node]

                if stepId is not None:
                    self.gpuDict.pop(node)
                    self.gpuDict[stepId] = gpus
                    logger.info("GPUs %s assigned to step %s" % (gpus, stepId))
                else:
                    logger.info("Free gpu slot found at %s" % node)
                return gpus

        return None
    def freeGpusSlot(self, node):
        gpus = self.gpuDict.get(node, None)

        # Some nodes/threads do not use gpus so may not be booked and not in the dictionary
        if gpus is not None:
            self.gpuDict.pop(node)
            self.gpuDict[-node] = gpus
            logger.info("GPUs %s freed from step %s" % (gpus, node))
        else:
            logger.debug("step id %s not found in GPU slots" % node)

    def _isStepRunnable(self, step):
        """ Overwrite this method to check GPUs availability"""

        if self.gpuList and step.needsGPU() and self.getFreeGpuSlot(step.getObjId()) is None:
            logger.info("Can't run step %s. Needs gpus and there are no free gpu slots" % step)
            return False

        return True

    def runSteps(self, steps, 
                 stepStartedCallback, 
                 stepFinishedCallback,
                 stepsCheckCallback,
                 stepsCheckSecs=5):
        """
        Creates threads and synchronize the steps execution.

        :param steps: list of steps to run
        :param stepStartedCallback: callback to be called before starting any step
        :param stepFinishedCallback: callback to be run after all steps are done
        :param stepsCheckCallback: callback to check if there are new steps to add (streaming)
        :param stepsCheckSecs: seconds between stepsCheckCallback calls

        """

        delta = datetime.timedelta(seconds=stepsCheckSecs)
        lastCheck = datetime.datetime.now()

        sharedLock = threading.Lock()

        runningSteps = {}  # currently running step in each node ({node: step})
        freeNodes = list(range(1, self.numberOfProcs+1))  # available nodes to send jobs
        logger.info("Execution threads: %s" % freeNodes)
        logger.info("Running steps using %s threads. 1 thread is used for this main proccess." % self.numberOfProcs)

        while True:
            # See which of the runningSteps are not really running anymore.
            # Update them and freeNodes, and call final callback for step.
            with sharedLock:
                nodesFinished = [node for node, step in runningSteps.items()
                                 if not step.isRunning()]
            doContinue = True
            for node in nodesFinished:
                step = runningSteps.pop(node)  # remove entry from runningSteps
                freeNodes.append(node)  # the node is available now
                self.freeGpusSlot(step.getObjId())
                # Notify steps termination and check if we should continue
                doContinue = stepFinishedCallback(step)
                if not doContinue:
                    break

            if not doContinue:
                break

            anyLaunched = False
            # If there are available nodes, send next runnable step.
            with sharedLock:
                if freeNodes:
                    runnableSteps = self._getRunnable(steps, len(freeNodes))

                    for step in runnableSteps:
                        # We found a step to work in, so let's start a new
                        # thread to do the job and book it.
                        anyLaunched = True
                        step.setRunning()
                        stepStartedCallback(step)
                        node = freeNodes.pop(0)  # take an available node
                        runningSteps[node] = step
                        logger.debug("Running step %s on node %s" % (step, node))
                        t = StepThread(step, sharedLock)
                        # won't keep process up if main thread ends
                        t.daemon = True
                        t.start()
                anyPending = self._arePending(steps)

            if not anyLaunched:
                if anyPending:  # nothing running
                    time.sleep(3)
                else:
                    break  # yeah, we are done, either failed or finished :)

            now = datetime.datetime.now()
            if now - lastCheck > delta:
                stepsCheckCallback()
                lastCheck = now

        stepsCheckCallback()

        # Wait for all threads now.
        for t in threading.enumerate():
            if t is not threading.current_thread():
                t.join()


class QueueStepExecutor(ThreadStepExecutor):
    def __init__(self, hostConfig, submitDict, nThreads, **kwargs):
        ThreadStepExecutor.__init__(self, hostConfig, nThreads, **kwargs)
        self.submitDict = submitDict
        # Command counter per thread
        self.threadCommands = {}

        if nThreads > 1:
            self.runJobs = ThreadStepExecutor.runSteps
        else:
            self.runJobs = StepExecutor.runSteps

        self.renameGpuIds()

    def renameGpuIds(self):
        """ Reorganize the gpus ids starting from 0 since the queue engine is the one assigning them.
        https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#env-vars """
        for threadId, gpuList in self.gpuDict.items():
            for i in range(len(gpuList)):
                self.gpuDict[threadId][i] = i

        logger.debug("Updated gpus ids rebase starting from 0: %s per thread" %self.gpuDict)

    def getThreadJobId(self, stepId):
        """ Returns the job id extension assigned to each thread/step """
        if not stepId in self.threadCommands:
            self.threadCommands[stepId] = 0

        self.threadCommands[stepId] += 1

        return self.threadCommands[stepId]

    def runJob(self, log, programName, params, numberOfMpi=1, numberOfThreads=1, env=None, cwd=None, executable=None):
        threadId = threading.current_thread().thId
        submitDict = dict(self.hostConfig.getQueuesDefault())
        submitDict.update(self.submitDict)
        threadJobId = self.getThreadJobId(threadId)
        subthreadId = '-%s-%s' % (threadId, threadJobId)
        submitDict['JOB_NAME'] = submitDict['JOB_NAME'] + subthreadId
        submitDict['JOB_SCRIPT'] = os.path.abspath(removeExt(submitDict['JOB_SCRIPT']) + subthreadId + ".job")
        submitDict['JOB_LOGS'] = os.path.join(getParentFolder(submitDict['JOB_SCRIPT']), submitDict['JOB_NAME'])

        logger.debug("Variables available for replacement in submission command are: %s" % submitDict)

        submitDict['JOB_COMMAND'] = process.buildRunCommand(programName, params, numberOfMpi,
                                                            self.hostConfig, env,
                                                            gpuList=self._getGPUListForCommand(programName, params),
                                                            context=submitDict)


        jobid = _submit(self.hostConfig, submitDict, cwd, env)
        self.protocol.appendJobId(jobid)  # append active jobs
        self.protocol._store(self.protocol._jobId)

        if (jobid is None) or (jobid == UNKNOWN_JOBID):
            logger.info("jobId is none therefore we set it to fail")
            raise Exception("Failed to submit to queue.")

        status = cts.STATUS_RUNNING
        wait = 3

        # Check status while job running
        # REVIEW this to minimize the overhead in time put by this delay check
        while _checkJobStatus(self.hostConfig, jobid) == cts.STATUS_RUNNING:
            time.sleep(wait)
            if wait < 300:
                wait += 3

        self.protocol.removeJobId(jobid)  # After completion, remove inactive jobs.
        self.protocol._store(self.protocol._jobId)

        return status
