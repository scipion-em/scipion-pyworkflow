# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (delarosatrevin@scilifelab.se) [1]
# *
# * [1] SciLifeLab, Stockholm University
# *
# * This program is free software: you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation, either version 3 of the License, or
# * (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program.  If not, see <https://www.gnu.org/licenses/>.
# *
# *  All comments concerning this program package may be sent to the
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************
"""
This modules contains classes required for the workflow
execution and tracking like: Step and Protocol
"""
import sys
import json
import threading
import time

import pyworkflow as pw
from pyworkflow.exceptions import ValidationException, PyworkflowException
from pyworkflow.object import *
import pyworkflow.utils as pwutils
from pyworkflow.utils.log import LoggingConfigurator, getExtraLogInfo, STATUS, setDefaultLoggingContext
from .executor import (StepExecutor, ThreadStepExecutor, MPIStepExecutor,
                       QueueStepExecutor)
from .constants import *
from .params import Form

SCHEDULE_LOG = 'schedule.log'

import  logging
# Get the root logger
logger = logging.getLogger(__name__)


class Step(Object):
    """ Basic execution unit.
    It should defines its Input, Output
    and define a run method.
    """

    def __init__(self, **kwargs):
        Object.__init__(self, **kwargs)
        self._prerequisites = CsvList()  # which steps needs to be done first
        self.status = String()
        self.initTime = String()
        self.endTime = String()
        self._error = String()
        self.interactive = Boolean(False)
        self._resultFiles = String()
        self._index = None

    def getIndex(self):
        return self._index

    def setIndex(self, newIndex):
        self._index = newIndex

    def getPrerequisites(self):
        return self._prerequisites

    def addPrerequisites(self, *newPrerequisites):
        for p in newPrerequisites:
            self._prerequisites.append(p)

    def setPrerequisites(self, *newPrerequisites):
        self._prerequisites.clear()
        self.addPrerequisites(*newPrerequisites)

    def _preconditions(self):
        """ Check if the necessary conditions to
        step execution are met"""
        return self._validate() == []

    def _postconditions(self):
        """ Check if the step have done well its task
        and accomplish its results"""
        return True

    def _run(self):
        """ This is the function that will do the real job.
        It should be override by sub-classes."""
        pass

    def setRunning(self):
        """ The the state as STATE_RUNNING and
        set the init and end times.
        """
        self.initTime.set(dt.datetime.now())
        self.endTime.set(None)
        self.status.set(STATUS_RUNNING)
        self._error.set(None)  # Clean previous error message

    def getError(self):
        return self._error

    def getErrorMessage(self):
        return self.getError().get('')

    def setFailed(self, msg):
        """ Set the run failed and store an error message. """
        self._finalizeStep(STATUS_FAILED, msg=msg)

    def setAborted(self):
        """ Set the status to aborted and updates the endTime. """
        self._finalizeStep(STATUS_ABORTED, "Aborted by user.")

    def setFinished(self):
        """ Set the status to finish updates the end time """
        self._finalizeStep(STATUS_FINISHED)

    def _finalizeStep(self, status, msg=None):
        """ Closes the step, setting up the endTime and optionally an error message"""
        self.endTime.set(dt.datetime.now())
        if msg:
            self._error.set(msg)
        self.status.set(status)

    def setSaved(self):
        """ Set the status to saved and updated the endTime. """
        self.initTime.set(None)
        self.endTime.set(None)
        self.status.set(STATUS_SAVED)
        self._error.set(None)  # Clean previous error message

    def getStatus(self):
        return self.status.get(STATUS_NEW)

    def getElapsedTime(self, default=dt.timedelta()):
        """ Return the time that took to run
        (or the actual running time if still is running )
        """
        elapsed = default

        if self.initTime.hasValue():
            t1 = self.initTime.datetime()

            if self.endTime.hasValue():
                t2 = self.endTime.datetime()
            else:
                t2 = dt.datetime.now()

            elapsed = t2 - t1

        return elapsed

    def setStatus(self, value):
        return self.status.set(value)

    def setInteractive(self, value):
        return self.interactive.set(value)

    def isActive(self):
        return self.getStatus() in ACTIVE_STATUS

    def isFinished(self):
        return self.getStatus() == STATUS_FINISHED

    def isRunning(self):
        return self.getStatus() == STATUS_RUNNING

    def isFailed(self):
        return self.getStatus() == STATUS_FAILED

    def isSaved(self):
        return self.getStatus() == STATUS_SAVED

    def isScheduled(self):
        return self.getStatus() == STATUS_SCHEDULED

    def isAborted(self):
        return self.getStatus() == STATUS_ABORTED

    def isLaunched(self):
        return self.getStatus() == STATUS_LAUNCHED

    def isInteractive(self):
        return self.interactive.get()

    def isWaiting(self):
        return self.getStatus() == STATUS_WAITING

    def run(self):
        """ Do the job of this step"""
        self.setRunning()
        try:
            self._run()
            self.endTime.set(dt.datetime.now())
            if self.status.get() == STATUS_RUNNING:
                if self.isInteractive():
                    # If the Step is interactive, after run
                    # it will be waiting for use to mark it as DONE
                    status = STATUS_INTERACTIVE
                else:
                    status = STATUS_FINISHED
                self.status.set(status)

        except PyworkflowException as e:
            print(pwutils.redStr(str(e)))
            self.setFailed(str(e))
        except Exception as e:
            self.setFailed(str(e))
            import traceback
            traceback.print_exc()
            # raise #only in development
            # finally:
            #     self.endTime.set(dt.datetime.now())


class FunctionStep(Step):
    """ This is a Step wrapper around a normal function
    This class will ease the insertion of Protocol function steps
    through the function _insertFunctionStep"""

    def __init__(self, func=None, funcName=None, *funcArgs, **kwargs):
        """
         Params:
            func: the function that will be executed.
            funcName: the name assigned to that function (will be stored)
            *funcArgs: argument list passed to the function (serialized and stored)
            **kwargs: extra parameters.
        """
        Step.__init__(self)
        self._func = func  # Function should be set before run
        self._args = funcArgs
        self.funcName = String(funcName)
        self.argsStr = String(json.dumps(funcArgs, default=lambda x: None))
        self.setInteractive(kwargs.get('interactive', False))
        if kwargs.get('wait', False):
            self.setStatus(STATUS_WAITING)

    def _runFunc(self):
        """ Return the possible result files after running the function. """
        return self._func(*self._args)

    def _run(self):
        """ Run the function and check the result files if any. """
        resultFiles = self._runFunc()
        if isinstance(resultFiles, str):
            resultFiles = [resultFiles]
        if resultFiles and len(resultFiles):
            missingFiles = pwutils.missingPaths(*resultFiles)
            if len(missingFiles):
                raise Exception('Missing filePaths: ' + ' '.join(missingFiles))
            self._resultFiles.set(json.dumps(resultFiles))

    def _postconditions(self):
        """ This type of Step, will simply check
        as postconditions that the result filePaths exists"""
        if not self._resultFiles.hasValue():
            return True
        filePaths = json.loads(self._resultFiles.get())

        return len(pwutils.missingPaths(*filePaths)) == 0

    def __eq__(self, other):
        """ Compare with other FunctionStep"""
        return (self.funcName == other.funcName and
                self.argsStr == other.argsStr)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.funcName.get()


class RunJobStep(FunctionStep):
    """ This Step will wrapper the commonly used function runJob
    for launching specific programs with some parameters.
    The runJob function should be provided by the protocol
    when inserting a new RunJobStep"""

    def __init__(self, runJobFunc=None, programName=None, arguments=None,
                 resultFiles=[], **kwargs):
        FunctionStep.__init__(self, runJobFunc, 'runJob', programName,
                              arguments)
        # Number of mpi and threads used to run the program
        self.__runJob = runJobFunc  # Store the current function to run the job
        self.mpi = 1
        self.threads = 1

    def _runFunc(self):
        """ Wrap around runJob function"""
        # We know that:
        #  _func: is the runJob function
        #  _args[0]: is the program name
        #  _args[1]: is the arguments to the program
        return self._func(None, self._args[0], self._args[1],
                          numberOfMpi=self.mpi, numberOfThreads=self.threads)
        # TODO: Add the option to return resultFiles

    def __str__(self):
        return self._args[0]  # return program name


class StepSet(Set):
    """ Special type of Set for storing steps. """

    def __init__(self, filename=None, prefix='',
                 mapperClass=None, **kwargs):
        Set.__init__(self, filename, prefix, mapperClass, classesDict=globals(),
                     **kwargs)


class Protocol(Step):
    """ The Protocol is a higher type of Step.
    It also have the inputs, outputs and other Steps properties,
    but contains a list of steps that are executed
    """

    # Version where protocol appeared first time
    _lastUpdateVersion = pw.VERSION_1
    _stepsCheckSecs = pw.Config.getStepsCheckSeconds()
    # Protocol develop status: PROD, BETA, NEW
    _devStatus = pw.PROD

    """" Possible Outputs:
    This is an optional but recommended attribute to fill.
    It has to be an enum with names being the name of the output and value the class of the output:
    
        class MyOutput(enum.Enum):
            outputMicrographs = SetOfMicrographs
            outputMicrographDW = SetOfMicrographs
    
    When defining outputs you can, optionally, use this enum like:
    self._defineOutputs(**{MyOutput.outputMicrographs.name, setOfMics})
    It will help to keep output names consistently
    
    Alternative an inline dictionary will work:
    _possibleOutputs = {"outputMicrographs" : SetOfMicrographs}
    
    For a more fine detailed/dynamic output based on parameters, you can overwrite the getter:
    getPossibleOutputs() in your protocol.
    
    """
    _possibleOutputs = None

    def __init__(self, **kwargs):
        Step.__init__(self, **kwargs)
        self._steps = []  # List of steps that will be executed
        # All generated filePaths should be inside workingDir
        self.workingDir = String(kwargs.get('workingDir', '.'))
        self.mapper = kwargs.get('mapper', None)
        self._inputs = []
        self._outputs = CsvList()
        # This flag will be used to annotate it output are already "migrated"
        #  and available in the _outputs list. Therefore iterating
        self._useOutputList = Boolean(False)
        # Expert level needs to be defined before parsing params
        self.expertLevel = Integer(kwargs.get('expertLevel', LEVEL_NORMAL))
        self._definition = Form(self)
        self._defineParams(self._definition)
        self._createVarsFromDefinition(**kwargs)
        self._log = logger
        self._buffer = ''  # text buffer for reading log files
        # Project to which the protocol belongs
        self.__project = kwargs.get('project', None)
        # Filename templates dict that will be used by _getFileName
        self.__filenamesDict = {}

        # This will be used at project load time to check if
        # we need to update the protocol with the data from run.db
        self.lastUpdateTimeStamp = String()

        # For non-parallel protocols mpi=1 and threads=1
        self.allowMpi = hasattr(self, 'numberOfMpi')
        if not self.allowMpi:
            self.numberOfMpi = Integer(1)

        self.allowThreads = hasattr(self, 'numberOfThreads')

        if not self.allowThreads:
            self.numberOfThreads = Integer(1)

        # Check if MPI or threads are passed in **kwargs, mainly used in tests
        if 'numberOfMpi' in kwargs:
            self.numberOfMpi.set(kwargs.get('numberOfMpi'))

        if 'numberOfThreads' in kwargs:
            self.numberOfThreads.set(kwargs.get('numberOfThreads'))

        if not hasattr(self, 'hostName'):
            self.hostName = String(kwargs.get('hostName', 'localhost'))

        if not hasattr(self, 'hostFullName'):
            self.hostFullName = String()

        # Maybe this property can be inferred from the
        # prerequisites of steps, but is easier to keep it
        self.stepsExecutionMode = STEPS_SERIAL

        # Run mode
        self.runMode = Integer(kwargs.get('runMode', MODE_RESUME))
        # Use queue system?
        self._useQueue = Boolean(False)
        # Store a json string with queue name
        # and queue parameters (only meaningful if _useQueue=True)
        self._queueParams = String()
        self.queueShown = False
        self._jobId = String()  # Store queue job id
        self._pid = Integer()
        self._stepsExecutor = None
        self._stepsDone = Integer(0)
        self._cpuTime = Integer(0)
        self._numberOfSteps = Integer(0)
        # For visualization
        self.allowHeader = Boolean(True)
        # Create an String variable to allow some protocol to precompute
        # the summary message
        self.summaryVar = String()
        self.methodsVar = String()
        # Create a variable to know if the protocol has expert params
        self._hasExpert = None

        # Store warnings here
        self.summaryWarnings = []
        # Get a lock for threading execution
        self._lock = threading.Lock()

    def _storeAttributes(self, attrList, attrDict):
        """ Store all attributes in attrDict as
        attributes of self, also store the key in attrList.
        """
        for key, value in attrDict.items():
            if key not in attrList:
                attrList.append(key)
            setattr(self, key, value)

    def _defineInputs(self, **kwargs):
        """ This function should be used to define
        those attributes considered as Input.
        """
        self._storeAttributes(self._inputs, kwargs)

    def _defineOutputs(self, **kwargs):
        """ This function should be used to specify
        expected outputs.
        """
        for k, v in kwargs.items():
            if hasattr(self, k):
                self._deleteChild(k, v)
            self._insertChild(k, v)

        # Store attributes in _output (this does not persist them!)
        self._storeAttributes(self._outputs, kwargs)

        # Persist outputs list
        self._insertChild("_outputs", self._outputs)
        self._useOutputList.set(True)
        self._insertChild("_useOutputList", self._useOutputList)

    def _closeOutputSet(self):
        """Close all output set"""
        for outputName, output in self.iterOutputAttributes():
            if isinstance(output, Set) and output.isStreamOpen():
                self.__tryUpdateOutputSet(outputName, output, state=Set.STREAM_CLOSED)

    def _updateOutputSet(self, outputName, outputSet,
                         state=Set.STREAM_OPEN):
        """ Use this function when updating an Stream output set.
        """
        self.__tryUpdateOutputSet(outputName, outputSet, state)

    def __tryUpdateOutputSet(self, outputName, outputSet,
                            state=Set.STREAM_OPEN, tries=1):
        try:
            # Update the set with the streamState value (either OPEN or CLOSED)
            outputSet.setStreamState(state)

            if self.hasAttribute(outputName):
                outputSet.write()  # Write to commit changes
                outputAttr = getattr(self, outputName)
                # Copy the properties to the object contained in the protocol
                outputAttr.copy(outputSet, copyId=False)
                # Persist changes
                self._store(outputAttr)
            else:
                # Here the defineOutputs function will call the write() method
                self._defineOutputs(**{outputName: outputSet})
                self._store(outputSet)
            # Close set database to avoid locking it
            outputSet.close()

        except Exception as ex:
            print("Error trying to update output of protocol, tries=%d" % tries)

            if tries > 3:
                raise ex
            else:
                time.sleep(tries)
                self.__tryUpdateOutputSet(outputName, outputSet, state,
                                          tries + 1)

    def hasExpert(self):
        """ This function checks if the protocol has
        any expert parameter"""
        if self._hasExpert is None:
            self._hasExpert = False
            for paraName, param in self._definition.iterAllParams():
                if param.isExpert():
                    self._hasExpert = True
                    break

        return self._hasExpert

    def getProject(self):
        return self.__project

    def setProject(self, project):
        self.__project = project

    @staticmethod
    def hasDefinition(cls):
        """ Check if the protocol has some definition.
        This can help to detect "abstract" protocol that
        only serve as base for other, not to be instantiated.
        """
        return hasattr(cls, '_definition')

    @classmethod
    def isNew(cls):
        if cls._devStatus == pw.NEW:
            return True
        elif cls._devStatus == pw.PROD:
            return cls._lastUpdateVersion not in pw.OLD_VERSIONS

    @classmethod
    def isBeta(cls):
        return cls._devStatus == pw.BETA

    def getDefinition(self):
        """ Access the protocol definition. """
        return self._definition

    def getParam(self, paramName):
        """ Return a _definition param give its name. """
        return self._definition.getParam(paramName)

    def getEnumText(self, paramName):
        """ This function will retrieve the text value
        of an enum parameter in the definition, taking the actual value in
        the protocol.
        Params:
            paramName: the name of the enum param.
        Returns:
            the string value corresponding to the enum choice.
        """
        index = getattr(self, paramName).get()
        return self.getParam(paramName).choices[index]

    def evalParamCondition(self, paramName):
        """ Eval if the condition of paramName in _definition
        is satisfied with the current values of the protocol attributes.
        """
        return self._definition.evalParamCondition(paramName)

    def evalExpertLevel(self, paramName):
        """ Return the expert level evaluation for a param with the given name.
        """
        return self.evalParamExpertLevel(self.getParam(paramName))

    def evalParamExpertLevel(self, param):
        """ Return True if the param has an expert level is less than
        the one for the whole protocol.
        """
        return param.expertLevel.get() <= self.expertLevel.get()

    def iterDefinitionAttributes(self):
        """ Iterate over all the attributes from definition. """
        for paramName, _ in self._definition.iterParams():
            yield paramName, getattr(self, paramName)

    def getDefinitionDict(self):
        """ Similar to getObjDict, but only for those
        params that are in the form.
        This function is used for export protocols as json text file.
        """
        d = OrderedDict()
        d['object.className'] = self.getClassName()
        d['object.id'] = self.strId()
        d['object.label'] = self.getObjLabel()
        d['object.comment'] = self.getObjComment()
        d['_useQueue'] = self._useQueue.getObjValue()
        d['_prerequisites'] = self._prerequisites.getObjValue()

        if self._queueParams:
            d['_queueParams'] = self._queueParams.get()

        od = self.getObjDict()

        for attrName in od:
            if self.getParam(attrName) is not None:
                d[attrName] = od[attrName]

        return d

    def processImportDict(self, importDict, importDir):
        """
        This function is used when we import a workflow from a json to process or
        adjust the json data for reproducibility purposes e.g. resolve relative paths
        Params:
        importDict: Dict of the protocol that we got from the json
        importDir: dir of the json we're importing
        """
        return importDict

    def iterDefinitionSections(self):
        """ Iterate over all the section of the definition. """
        for section in self._definition.iterSections():
            yield section

    def iterInputAttributes(self):
        """ Iterate over the main input parameters
        of this protocol. Now the input are assumed to be these attribute
        which are pointers and have no condition.
        """
        for key, attr in self.getAttributes():
            if not isinstance(attr, Object):
                raise Exception('Attribute %s have been overwritten to type %s '
                                % (key, type(attr)))
            if isinstance(attr, PointerList) and attr.hasValue():
                for item in attr:
                    # the same key is returned for all items inside the
                    # PointerList, this is used in viewprotocols.py
                    # to group them inside the same tree element
                    yield key, item
            if attr.isPointer() and attr.hasValue():
                yield key, attr

            # Consider here scalars with pointers inside
            elif isinstance(attr, Scalar) and attr.hasPointer():
                if attr.get() is not None:
                    yield key, attr.getPointer()

    def iterInputPointers(self):
        """ This function is similar to iterInputAttributes, but it yields
        all input Pointers, independently if they have value or not.
        """
        for key, attr in self.getAttributes():
            if not isinstance(attr, Object):
                raise Exception('Attribute %s have been overwritten to type %s '
                                % (key, type(attr)))
            if isinstance(attr, PointerList) and attr.hasValue():
                for item in attr:
                    # the same key is returned for all items inside the
                    # PointerList, this is used in viewprotocols.py
                    # to group them inside the same tree element
                    yield key, item
            elif attr.isPointer():
                yield key, attr

    def inputProtocolDict(self):
        """
        This function returns a dictionary of protocols that need to update
        their database to launch this protocol (this method is only used
        when a WORKFLOW is restarted or continued).
        Actions done here are:
        1. Iterate over the main input Pointer of this protocol
           (here, 3 different cases are analyzed)

           A) When the pointer points to a protocol

           B) When the pointer points to another object (INDIRECTLY).
              - The pointer has an _extended value (new parameters configuration
                in the protocol)

           C) When the pointer points to another object (DIRECTLY).
              - The pointer has not an _extended value (old parameters
                configuration in the protocol)

        2. The PROTOCOL to which the pointer points is determined and saved in
           the dictionary

        3. If this pointer points to another object (case B and C):
           - Iterate over the main attributes of this pointer
           - if any attribute is a pointer, then we move to PROTOCOL and repeat
             this procedure from step 1
        """
        protocolDict = {}
        protocol = None
        for key, attrInput in self.iterInputAttributes():
            output = attrInput.get()
            if isinstance(output, Protocol):  # case A
                protocol = output
            else:
                if attrInput.hasExtended():  # case B
                    protocol = attrInput.getObjValue()
                else:  # case C

                    if self.getProject() is not None:
                        protocol = self.getProject().getRunsGraph(refresh=True).getNode(str(output.getObjParentId())).run
                    else:
                        # This is a problem, since protocols coming from
                        # Pointers do not have the __project set.
                        # We do not have an clear way to get the protocol if
                        # we do not have the project object associated
                        # This case implies Direct Pointers to Sets
                        # (without extended): hopefully this will only be
                        # created from tests
                        print("Can't get protocol info from input attribute."
                              " This could render unexpected results when "
                              "scheduling protocols.")
                        continue

                if output is not None:
                    for k, attr in output.getAttributes():
                        if isinstance(attr, Pointer):
                            if attr.get() is not None:
                                auxDict = protocol.inputProtocolDict()
                                for auxKey in auxDict:
                                    if auxKey not in protocolDict.keys():
                                        protocolDict[auxKey] = auxDict[auxKey]
                                break

            protocolDict[protocol.getObjId()] = protocol

        return protocolDict

    def getInputStatus(self):
        """ Returns if any input pointer is not ready yet and if there is
         any pointer to an open set
        """
        emptyPointers = False
        openSetPointer = False

        for paramName, attr in self.iterInputPointers():

            param = self.getParam(paramName)
            # Issue #1597: New data loaded with old code.
            # If the input pointer is not a param:
            # This could happen in backward incompatibility cases,
            # Protocol has an attribute (inputPointer) but class does not define
            # if in the define params.
            if param is None:
                print("%s attribute is not defined as parameter. "
                      "This could happen when loading new code with older "
                      "scipion versions." % paramName)
                continue

            condition = self.evalParamCondition(paramName)

            obj = attr.get()
            if condition and obj is None and not param.allowsNull:
                if not attr.hasValue():
                   emptyPointers = True

            if not self.worksInStreaming() and isinstance(obj, Set) and obj.isStreamOpen():
                openSetPointer = True

        return emptyPointers, openSetPointer

    def iterOutputAttributes(self, outputClass=None, includePossible=False):
        """ Iterate over the outputs produced by this protocol. """

        iterator = self._iterOutputsNew if self._useOutputList else self._iterOutputsOld

        hasOutput=False

        # Iterate through actual outputs
        for key, attr in iterator():
            if outputClass is None or isinstance(attr, outputClass):
                hasOutput = True
                yield key, attr

        # NOTE: This will only happen in case there is no actual output.
        # There is no need to avoid duplication of actual output and possible output.
        if includePossible and not hasOutput and self.getPossibleOutputs() is not None:
            for possibleOutput in self.getPossibleOutputs():
                if isinstance(possibleOutput, str):
                    yield possibleOutput, self._possibleOutputs[possibleOutput]
                else:
                    yield possibleOutput.name, possibleOutput.value

    def getPossibleOutputs(self):
        return self._possibleOutputs

    def _iterOutputsNew(self):
        """ This methods iterates through a list where outputs have been
        annotated"""

        # Loop through the output list
        for attrName in self._outputs:

            # FIX: When deleting manually an output, specially for interactive protocols.
            # The _outputs is properly deleted in projects.sqlite, not it's run.db remains.
            # When the protocol is updated from run.db it brings the outputs that were deleted
            if hasattr(self, attrName):
                # Get it from the protocol
                attr = getattr(self, attrName)

                yield attrName, attr
            else:
                self._outputs.remove(attrName)

    def _iterOutputsOld(self):
        """ This method iterates assuming the old model: any EMObject attribute
        is an output."""
        # Iterate old Style:

        try:
            domain = self.getClassDomain()
        except Exception as e:
            print(e)
            print("Protocol in workingdir ", self.getWorkingDir(), " is of an unknown class")
            print("Maybe the class name has changed")
            return "none", None

        for key, attr in self.getAttributes():
            if isinstance(attr, domain._objectClass):
                yield key, attr
                return

    def isInStreaming(self):
        # For the moment let's assume a protocol is in streaming
        # if at least one of the output sets is in STREAM_OPEN state
        for paramName, attr in self.iterOutputAttributes():
            if isinstance(attr, Set):
                if attr.isStreamOpen():
                    return True
        return False

    @classmethod
    def worksInStreaming(cls):
        # A protocol should work in streaming if it implements the stepCheck()
        # Get the stepCheck method from the Protocol
        baseStepCheck = Protocol._stepsCheck
        ownStepCheck = cls._stepsCheck

        return not pwutils.isSameFunction(baseStepCheck, ownStepCheck)

    def allowsGpu(self):
        """ Returns True if this protocol allows GPU computation. """
        return self.hasAttribute(GPU_LIST)

    def requiresGpu(self):
        """ Return True if this protocol can only be executed in GPU. """
        return self.allowsGpu() and not self.hasAttribute(USE_GPU)

    def usesGpu(self):
        return self.allowsGpu() and self.getAttributeValue(USE_GPU, True)

    def getGpuList(self):
        if not self.allowsGpu():
            return []

        return pwutils.getListFromRangeString(self.gpuList.get())

    def getOutputsSize(self):
        return sum(1 for _ in self.iterOutputAttributes())

    def getOutputFiles(self):
        """ Return the output files produced by this protocol.
        This can be used in web to download or in remote
        executions to copy results back.
        """
        # By default return the output file of each output attribute
        s = set()

        for _, attr in self.iterOutputAttributes():
            s.update(attr.getFiles())

        return s

    def copyDefinitionAttributes(self, other):
        """ Copy definition attributes to other protocol. """
        for paramName, _ in self.iterDefinitionAttributes():
            self.copyAttributes(other, paramName)

    def _createVarsFromDefinition(self, **kwargs):
        """ This function will setup the protocol instance variables
        from the Protocol Class definition, taking into account
        the variable type and default values.
        """
        if hasattr(self, '_definition'):
            for paramName, param in self._definition.iterParams():
                # Create the var with value coming from kwargs or from
                # the default param definition
                var = param.paramClass(value=kwargs.get(paramName,
                                                        param.default.get()))
                setattr(self, paramName, var)
        else:
            print("FIXME: Protocol '%s' has not DEFINITION"
                  % self.getClassName())

    def _getFileName(self, key, **kwargs):
        """ This function will retrieve filenames given a key and some
        keywords arguments. The __filenamesDict attribute should be
        updated with templates that accept the given keys.
        """
        return self.__filenamesDict[key] % kwargs

    def _updateFilenamesDict(self, fnDict):
        """ Update the dictionary with templates that will be used
        by the _getFileName function.
        """
        self.__filenamesDict.update(fnDict)

    def _store(self, *objs):
        """ Stores objects of the protocol using the mapper.
        If not objects are passed, the whole protocol is stored.
        """
        if self.mapper is not None:
            with self._lock:
                if len(objs) == 0:
                    self.mapper.store(self)
                else:
                    for obj in objs:
                        self.mapper.store(obj)
                self.mapper.commit()

    def _insertChild(self, key, child):
        """ Insert a new child not stored previously.
        If stored previously, _store should be used.
        The child will be set as self.key attribute
        """
        try:
            setattr(self, key, child)
            if self.hasObjId():
                self.mapper.insertChild(self, key, child)
        except Exception as ex:
            print("Error with child '%s', value=%s, type=%s"
                  % (key, child, type(child)))
            raise ex

    def _deleteChild(self, key, child):
        """ Delete a child from the mapper. """
        self.mapper.delete(child)

    def _insertAllSteps(self):
        """ Define all the steps that will be executed. """
        pass

    def _defineParams(self, form):
        """ Define the input parameters that will be used.
        Params:
            form: this is the form to be populated with sections and params.
        """
        pass

    def __insertStep(self, step, **kwargs):
        """ Insert a new step in the list.
        Params:
         **kwargs:
            prerequisites: a list with the steps index that need to be done
                           previous than the current one."""
        prerequisites = kwargs.get('prerequisites', None)

        if prerequisites is None:
            if len(self._steps):
                # By default add the previous step as prerequisite
                step.addPrerequisites(len(self._steps))
        else:
            step.addPrerequisites(*prerequisites)

        self._steps.append(step)
        # Setup and return step index
        step.setIndex(len(self._steps))

        return step.getIndex()

    def setRunning(self):
        """ Do not reset the init time in RESUME_MODE"""
        previousStart = self.initTime.get()
        super().setRunning()
        if self.getRunMode() == MODE_RESUME and previousStart is not None:
            self.initTime.set(previousStart)
        else:
            self._cpuTime.set(0)

    def setAborted(self):
        """ Abort the protocol, finalize the steps and close all open sets"""
        try:
            super().setAborted()
            self._updateSteps(lambda step: step.setAborted(), where="status='%s'" % STATUS_RUNNING)
            self._closeOutputSet()
        except Exception as e:
            print("An error occurred aborting the protocol (%s)" % e)

    def setFailed(self, msg):
        """ Set the run failed and close all open  sets. """
        super().setFailed(msg)
        self._closeOutputSet()

    def _updateSteps(self, updater, where="1"):
        """Set the status of all steps
        :parameter updater callback/lambda receiving a step and editing it inside
        :parameter where condition to filter the set with."""
        stepsSet = StepSet(filename=self.getStepsFile())
        for step in stepsSet.iterItems(where=where):
            updater(step)
            stepsSet.update(step)
        stepsSet.write()
        stepsSet.close()  # Close the connection

    def _getPath(self, *paths):
        """ Return a path inside the workingDir. """
        return os.path.join(self.workingDir.get(), *paths)

    def _getExtraPath(self, *paths):
        """ Return a path inside the extra folder. """
        return self._getPath("extra", *paths)

    def _getTmpPath(self, *paths):
        """ Return a path inside the tmp folder. """
        return self._getPath("tmp", *paths)

    def _getLogsPath(self, *paths):
        return self._getPath("logs", *paths)

    def _getRelPath(self, *path):
        """ Return a relative path from the workingDir. """
        return os.path.relpath(self._getPath(*path), self.workingDir.get())

    def _getRelPathExecutionDir(self, *path):
        """ Return a relative path from the projdir. """
        # TODO  must be a bettis
        return os.path.relpath(
            self._getPath(*path),
            os.path.dirname(os.path.dirname(self.workingDir.get()))
        )

    def _getBasePath(self, path):
        """ Take the basename of the path and get the path
        relative to working dir of the protocol.
        """
        return self._getPath(os.path.basename(path))

    def _insertFunctionStep(self, func, *funcArgs, **kwargs):
        """
         Params:
           func: the function itself or, optionally, the name (string) of the function to be run in the Step.
           *funcArgs: the variable list of arguments to pass to the function.
           **kwargs: see __insertStep
        """
        if isinstance(func, str):
            # Get the function give its name
            func = getattr(self, func, None)

        # Ensure the protocol instance have it and is callable
        if not func:
            raise Exception("Protocol._insertFunctionStep: '%s' function is "
                            "not member of the protocol" % func)
        if not callable(func):
            raise Exception("Protocol._insertFunctionStep: '%s' is not callable"
                            % func)
        step = FunctionStep(func, func.__name__, *funcArgs, **kwargs)

        return self.__insertStep(step, **kwargs)

    def _insertRunJobStep(self, progName, progArguments, resultFiles=[],
                          **kwargs):
        """ Insert an Step that will simple call runJob function
        **args: see __insertStep
        """
        return self._insertFunctionStep('runJob', progName, progArguments,
                                        **kwargs)

    def _insertCopyFileStep(self, sourceFile, targetFile, **kwargs):
        """ Shortcut function to insert an step for copying a file to a destiny. """
        step = FunctionStep(pwutils.copyFile, 'copyFile', sourceFile,
                            targetFile,
                            **kwargs)
        return self.__insertStep(step, **kwargs)

    def _enterDir(self, path):
        """ Enter into a new directory path and store the current path.
        The current path will be used in _leaveDir, but nested _enterDir
        are not allowed since self._currentDir is overwritten.
        """
        self._currentDir = os.getcwd()
        os.chdir(path)
        if self._log:
            self._log.info("Entered into dir: cd '%s'" % path)

    def _leaveDir(self):
        """ This method should be called after a call to _enterDir
        to return to the previous location.
        """
        os.chdir(self._currentDir)
        if self._log:
            self._log.info("Returned to dir: cd '%s'" % self._currentDir)

    def _enterWorkingDir(self):
        """ Change to the protocol working dir. """
        self._enterDir(self.workingDir.get())

    def _leaveWorkingDir(self):
        """ This function make sense to use in conjunction
        with _enterWorkingDir to go back to execution path.
        """
        self._leaveDir()

    def continueFromInteractive(self):
        """ TODO: REMOVE this function.
        Check if there is an interactive step and set
        as finished, this is used now mainly in picking,
        but we should remove this since is weird for users.
        """
        if os.path.exists(self.getStepsFile()):
            stepsSet = StepSet(filename=self.getStepsFile())
            for step in stepsSet:
                if step.getStatus() == STATUS_INTERACTIVE:
                    step.setStatus(STATUS_FINISHED)
                    stepsSet.update(step)
                    break
            stepsSet.write()
            stepsSet.close()  # Close the connection

    def loadSteps(self):
        """ Load the Steps stored in the steps.sqlite file.
        """
        prevSteps = []

        if os.path.exists(self.getStepsFile()):
            stepsSet = StepSet(filename=self.getStepsFile())
            for step in stepsSet:
                prevSteps.append(step.clone())
            stepsSet.close()  # Close the connection
        return prevSteps

    def _insertPreviousSteps(self):
        """ Insert steps of previous execution.
        It can be used to track previous steps done for
        protocol that allow some kind of continue (such as ctf estimation).
        """
        for step in self.loadSteps():
            self.__insertStep(step)

    def __findStartingStep(self):
        """ From a previous run, compare self._steps and self._prevSteps
        to find which steps we need to start at, skipping successful done
        and not changed steps. Steps that needs to be done, will be deleted
        from the previous run storage.
        """
        if self.runMode == MODE_RESTART:
            self._prevSteps = []
            return 0

        self._prevSteps = self.loadSteps()

        n = min(len(self._steps), len(self._prevSteps))
        self.debug("len(steps) %s len(prevSteps) %s "
                   % (len(self._steps), len(self._prevSteps)))

        for i in range(n):
            newStep = self._steps[i]
            oldStep = self._prevSteps[i]
            if (not oldStep.isFinished() or newStep != oldStep
                    or not oldStep._postconditions()):
                if pw.Config.debugOn():
                    self.info("Starting at step %d" % i)
                    self.info("     Old step: %s, args: %s"
                              % (oldStep.funcName, oldStep.argsStr))
                    self.info("     New step: %s, args: %s"
                              % (newStep.funcName, newStep.argsStr))
                    self.info("     not oldStep.isFinished(): %s"
                              % (not oldStep.isFinished()))
                    self.info("     newStep != oldStep: %s"
                              % (newStep != oldStep))
                    self.info("     not oldStep._postconditions(): %s"
                              % (not oldStep._postconditions()))
                return i
            newStep.copy(oldStep)

        return n

    def _storeSteps(self):
        """ Store the new steps list that can be retrieved
        in further execution of this protocol.
        """
        stepsFn = self.getStepsFile()

        self._stepsSet = StepSet(filename=stepsFn)
        self._stepsSet.setStore(False)
        self._stepsSet.clear()

        for step in self._steps:
            step.cleanObjId()
            self.setInteractive(self.isInteractive() or step.isInteractive())
            self._stepsSet.append(step)

        self._stepsSet.write()

    def __updateStep(self, step):
        """ Store a given step and write changes. """
        self._stepsSet.update(step)
        self._stepsSet.write()

    def _stepStarted(self, step):
        """This function will be called whenever an step
        has started running.
        """
        self.info(pwutils.magentaStr("STARTED") + ": %s, step %d, time %s" %
                  (step.funcName.get(), step._index, step.initTime.datetime()),
                  extra=getExtraLogInfo("PROTOCOL", STATUS.START,
                                        project_name=self.getProject().getName(),
                                        prot_id=self.getObjId(),
                                        prot_name=self.getClassName(),
                                        step_id=step._index))
        self.__updateStep(step)

    def _stepFinished(self, step):
        """This function will be called whenever an step
        has finished its run.
        """
        doContinue = True
        if step.isInteractive():
            doContinue = False
        elif step.isFailed():
            doContinue = False
            errorMsg = pwutils.redStr(
                "Protocol failed: " + step.getErrorMessage())
            self.setFailed(errorMsg)
            self.error(errorMsg)
        self.lastStatus = step.getStatus()

        self.__updateStep(step)
        self._stepsDone.increment()
        self._cpuTime.set(self._cpuTime.get() + step.getElapsedTime().total_seconds())
        self._store(self._stepsDone,  self._cpuTime)

        self.info(pwutils.magentaStr(step.getStatus().upper()) + ": %s, step %d, time %s"
                  % (step.funcName.get(), step._index, step.endTime.datetime()),
                  extra=getExtraLogInfo("PROTOCOL",STATUS.STOP,
                                        project_name=self.getProject().getName(),
                                        prot_id=self.getObjId(),
                                        prot_name=self.getClassName(),
                                        step_id=step._index))
        if step.isFailed() and self.stepsExecutionMode == STEPS_PARALLEL:
            # In parallel mode the executor will exit to close
            # all working threads, so we need to close
            self._endRun()
        return doContinue

    def _stepsCheck(self):
        pass

    def _runSteps(self, startIndex):
        """ Run all steps defined in self._steps. """
        self._stepsDone.set(startIndex)
        self._numberOfSteps.set(len(self._steps))
        self.setRunning()
        # Keep the original value to set in sub-protocols
        self._originalRunMode = self.runMode.get()
        # Always set to resume, even if set to restart
        self.runMode.set(MODE_RESUME)
        self._store()

        if startIndex == len(self._steps):
            self.lastStatus = STATUS_FINISHED
            self.info("All steps seem to be FINISHED, nothing to be done.")
        else:
            self.lastStatus = self.status.get()
            self._stepsExecutor.runSteps(self._steps,
                                         self._stepStarted,
                                         self._stepFinished,
                                         self._stepsCheck,
                                         self._stepsCheckSecs)

        print("*** Last status is %s " % self.lastStatus)
        self.setStatus(self.lastStatus)
        self._store(self.status)

    def __deleteOutputs(self):
        """ This function should only be used from RESTART.
        It will remove output attributes from mapper and object.
        """
        attributes = [a[0] for a in self.iterOutputAttributes()]

        for attrName in attributes:
            attr = getattr(self, attrName)
            self.mapper.delete(attr)
            delattr(self, attrName)

        self._outputs.clear()
        self.mapper.store(self._outputs)

    def findAttributeName(self, attr2Find):
        for attrName, attr in self.iterOutputAttributes():
            if attr.getObjId() == attr2Find.getObjId():
                return attrName
        return None

    def deleteOutput(self, output):
        attrName = self.findAttributeName(output)
        self.mapper.delete(output)
        delattr(self,attrName)
        if attrName in self._outputs:
            self._outputs.remove(attrName)
        self.mapper.store(self._outputs)
        self.mapper.commit()

    def __copyRelations(self, other):
        """ This will copy relations from protocol other to self """
        pass

    def copy(self, other, copyId=True, excludeInputs=False):
        # Input attributes list
        inputAttributes = []

        # If need to exclude input attributes
        if excludeInputs:
            # Get all the input attributes, to be ignored at copy():
            for key, attr in self.iterInputAttributes():
                inputAttributes.append(key)

        copyDict = Object.copy(self, other, copyId, inputAttributes)
        self._store()
        self.mapper.deleteRelations(self)

        for r in other.getRelations():
            rName = r['name']
            rCreator = r['parent_id']
            rParent = r[OBJECT_PARENT_ID]
            rChild = r['object_child_id']
            rParentExt = r['object_parent_extended']
            rChildExt = r['object_child_extended']

            if rParent in copyDict:
                rParent = copyDict.get(rParent).getObjId()

            if rChild in copyDict:
                rChild = copyDict.get(rChild).getObjId()

            self.mapper.insertRelationData(rName, rCreator, rParent, rChild,
                                           rParentExt, rChildExt)

    def getRelations(self):
        """ Return the relations created by this protocol. """
        return self.mapper.getRelationsByCreator(self)

    def _defineRelation(self, relName, parentObj, childObj):
        """ Insert a new relation in the mapper using self as creator. """
        parentExt = None
        childExt = None

        if parentObj.isPointer():
            parentExt = parentObj.getExtended()
            parentObj = parentObj.getObjValue()

        if childObj.isPointer():
            childExt = childObj.getExtended()
            childObj = childObj.getObjValue()

        self.mapper.insertRelation(relName, self, parentObj, childObj,
                                   parentExt, childExt)

    def makePathsAndClean(self):
        """ Create the necessary path or clean
        if in RESTART mode.
        """
        # Clean working path if in RESTART mode
        if self.runMode == MODE_RESTART:
            self.cleanWorkingDir()
            self.__deleteOutputs()
            # Delete the relations created by this protocol
            # (delete this in both project and protocol db)
            self.mapper.deleteRelations(self)
        self.makeWorkingDir()

    def cleanWorkingDir(self):
        """
        Delete all files and subdirectories related with the protocol
        """
        self.cleanTmp()
        pwutils.cleanPath(self._getPath())

    def makeWorkingDir(self):
        # Create workingDir, logs and extra paths
        paths = [self._getPath(), self._getExtraPath(), self._getLogsPath()]
        pwutils.makePath(*paths)
        # Create scratch if SCIPION_SCRATCH environment variable exist.
        # In other case, tmp folder is created
        pwutils.makeTmpPath(self)

    def cleanTmp(self):
        """ Delete all files and subdirectories under Tmp folder. """
        tmpFolder = self._getTmpPath()

        if os.path.islink(tmpFolder):
            pwutils.cleanPath(os.path.realpath(tmpFolder))
            os.remove(tmpFolder)
        else:
            pwutils.cleanPath(tmpFolder)

    def _run(self):
        # Check that a proper Steps executor have been set
        if self._stepsExecutor is None:
            raise Exception('Protocol.run: Steps executor should be set before '
                            'running protocol')
        # Check the parameters are correct
        errors = self.validate()
        if len(errors):
            raise ValidationException(
                'Protocol has validation errors:\n' + '\n'.join(errors))

        self._insertAllSteps()  # Define steps for execute later
        # Find at which step we need to start
        startIndex = self.__findStartingStep()
        self.info(" Starting at step: %d" % (startIndex + 1))
        self._storeSteps()
        self.info(" Running steps ")
        self._runSteps(startIndex)

    def _getEnviron(self):
        """ This function should return an environ variable
        that will be used when running new programs.
        By default, the protocol will use the one defined
        in the package that it belongs or None.
        """
        return self.getClassPackage().Plugin.getEnviron()

    def runJob(self, program, arguments, **kwargs):
        if self.stepsExecutionMode == STEPS_SERIAL:
            kwargs['numberOfMpi'] = kwargs.get('numberOfMpi',
                                               self.numberOfMpi.get())
            kwargs['numberOfThreads'] = kwargs.get('numberOfThreads',
                                                   self.numberOfThreads.get())
        else:
            kwargs['numberOfMpi'] = kwargs.get('numberOfMpi', 1)
            kwargs['numberOfThreads'] = kwargs.get('numberOfThreads', 1)
        if 'env' not in kwargs:
            kwargs['env'] = self._getEnviron()

        self._stepsExecutor.runJob(self._log, program, arguments, **kwargs)

    def run(self):
        """ Before calling this method, the working dir for the protocol
        to run should exists.
        """
        try:
            LoggingConfigurator.setUpProtocolRunLogging(self.getLogPaths()[0], self.getLogPaths()[1] )

            self.info(pwutils.greenStr('RUNNING PROTOCOL -----------------'))
            self.info("Protocol starts", extra=getExtraLogInfo("PROTOCOL", STATUS.START,
                                                               project_name=self.getProject().getName(),
                                                               prot_id=self.getObjId(),
                                                               prot_name=self.getClassName()))
            # Store the full machine name where the protocol is running
            # and also its PID
            self.setPid(os.getpid())
            self.setHostFullName(pwutils.getHostFullName())

            self.info('Hostname: %s' % self.getHostFullName())
            self.info('PID: %s' % self.getPid())
            self.info('pyworkflow: %s' % pw.__version__)
            self.info('plugin: %s' % self.getClassPackageName())
            if hasattr(self.getClassPackage(), "__version__"):
                self.info('plugin v: %s' % self.getClassPackage().__version__)
            self.info('currentDir: %s' % os.getcwd())
            self.info('workingDir: %s' % self.workingDir)
            self.info('runMode: %s' % MODE_CHOICES[self.runMode.get()])
            try:
                self.info('          MPI: %d' % self.numberOfMpi)
                self.info('      threads: %d' % self.numberOfThreads)
            except Exception as e:
                self.info('  * Cannot get information about MPI/threads (%s)' % e)
        # Something went wrong ans at this point status is launched. We mark it as failed.
        except Exception as e:
            print(e)
            self.setFailed(str(e))
            self._store(self.status, self.getError())
            self._endRun()
            return

        Step.run(self)
        if self.isFailed():
            self._store()
        self._endRun()

    def _endRun(self):
        """ Print some ending message and close some files. """
        # self._store()
        self._store(self.summaryVar)
        self._store(self.methodsVar)
        self._store(self.endTime)

        if pwutils.envVarOn(pw.SCIPION_DEBUG_NOCLEAN):
            self.warning('Not cleaning temp folder since '
                         '%s is set to True.' % pw.SCIPION_DEBUG_NOCLEAN)
        elif not self.isFailed():
            self.info('Cleaning temp folder....')
            self.cleanTmp()

        self.info(pwutils.greenStr('------------------- PROTOCOL ' +
                                   self.getStatusMessage().upper()),
                  extra=getExtraLogInfo("PROTOCOL",STATUS.STOP,
                                        project_name=self.getProject().getName(),
                                        prot_id=self.getObjId(),
                                        prot_name=self.getClassName()))


    def getLogPaths(self):
        return list(map(self._getLogsPath,
                        ['run.stdout', 'run.stderr', SCHEDULE_LOG]))

    def getScheduleLog(self):
        return self._getLogsPath(SCHEDULE_LOG)

    def getSteps(self):
        """ Return the steps.sqlite file under logs directory. """
        return self._steps

    def getStepsFile(self):
        """ Return the steps.sqlite file under logs directory. """
        return self._getLogsPath('steps.sqlite')


    def _addChunk(self, txt, fmt=None):
        """
        Add text txt to self._buffer, with format fmt.
        fmt can be a color (like 'red') or a link that looks like 'link:url'.
        """
        # Make the text html-safe first.
        for x, y in [('&', 'amp'), ('<', 'lt'), ('>', 'gt')]:
            txt = txt.replace(x, '&%s;' % y)

        if fmt is None:
            self._buffer += txt
        elif fmt.startswith('link:'):
            url = fmt[len('link:'):]
            # Add the url in the TWiki style
            if url.startswith('http://'):
                self._buffer += '[[%s][%s]]' % (url, txt)
            # Web does not exist, webtools must find a solution for this case.
            # else:
            #     from pyworkflow.web.pages import settings as django_settings
            #     absolute_url = django_settings.ABSOLUTE_URL
            #     self._buffer += '[[%s/get_log/?path=%s][%s]]' % (absolute_url,
            #                                                     url, txt)
        else:
            self._buffer += '<font color="%s">%s</font>' % (fmt, txt)

    def getLogsAsStrings(self):

        outputs = []
        for fname in self.getLogPaths():
            if pwutils.exists(fname):
                self._buffer = ''
                pwutils.renderTextFile(fname, self._addChunk)
                outputs.append(self._buffer)
            else:
                outputs.append('File "%s" does not exist' % fname)
        return outputs

    def getLogsLastLines(self, lastLines=None, logFile=0):
        """
        Get the last(lastLines) lines of a log file.

        :param lastLines, if None, will try 'PROT_LOGS_LAST_LINES' env variable, otherwise 20
        :param logFile: Log file to take the lines from, default = 0 (std.out). 1 for stdErr.
        """
        if not lastLines:
            lastLines = int(os.environ.get('PROT_LOGS_LAST_LINES', 20))

        # Get stdout
        stdoutFn =self.getLogPaths()[logFile]

        if not os.path.exists(stdoutFn):
            return []

        with  open(stdoutFn, 'r') as stdout:

            iterlen = lambda it: sum(1 for _ in it)
            numLines = iterlen(stdout)

            lastLines = min(lastLines, numLines)
            sk = numLines - lastLines
            sk = max(sk, 0)

            stdout.seek(0, 0)
            output = [l.strip('\n') for k, l in enumerate(stdout)
                      if k >= sk]
            return output

    def warning(self, message, redirectStandard=True):
        self._log.warning(message)

    def info(self, message, extra=None):
        self._log.info(message, extra= extra)

    def error(self, message, redirectStandard=True):
        self._log.error(message)

    def debug(self, message):
        self._log.debug(message)

    def getWorkingDir(self):
        return self.workingDir.get()

    def setWorkingDir(self, path):
        self.workingDir.set(path)

    def setMapper(self, mapper):
        """ Set a new mapper for the protocol to persist state. """
        self.mapper = mapper

    def getMapper(self):
        return self.mapper

    def getDbPath(self):
        return self._getLogsPath('run.db')

    def setStepsExecutor(self, executor=None):
        if executor is None:
            executor = StepExecutor(self.getHostConfig())

        self._stepsExecutor = executor

    def getFiles(self):
        resultFiles = set()
        for paramName, _ in self.getDefinition().iterPointerParams():
            # Get all self attribute that are pointers
            attrPointer = getattr(self, paramName)
            obj = attrPointer.get()  # Get object pointer by the attribute
            if hasattr(obj, 'getFiles'):
                resultFiles.update(obj.getFiles())  # Add files if any
        return resultFiles | pwutils.getFiles(self.workingDir.get())

    def getHostName(self):
        """ Get the execution host name.
         This value is only the key of the host in the configuration file.
        """
        return self.hostName.get()

    def setHostName(self, hostName):
        """ Set the execution host name (the host key in the config file) """
        self.hostName.set(hostName)

    def getHostFullName(self):
        """ Return the full machine name where the protocol is running. """
        return self.hostFullName.get()

    def setHostFullName(self, hostFullName):
        self.hostFullName.set(hostFullName)

    def getHostConfig(self):
        """ Return the configuration host. """
        return self.hostConfig

    def setHostConfig(self, config):
        self.hostConfig = config
        # Never store the host config as part of the protocol, it is kept
        # in the configuration information, the hostname is enough
        self.hostConfig.setStore(False)

    def getJobId(self):
        """ Return the jobId associated to a running protocol. """
        return self._jobId.get()

    def setJobId(self, jobId):
        self._jobId.set(jobId)

    def getPid(self):
        return self._pid.get()

    def setPid(self, pid):
        self._pid.set(pid)

    def getRunName(self):
        runName = self.getObjLabel().strip()
        if not len(runName):
            runName = self.getDefaultRunName()
        return runName

    def getDefaultRunName(self):
        return '%s.%s' % (self.getClassName(), self.strId())

    @classmethod
    def getClassPackage(cls):
        """ Return the package module to which this protocol belongs.
        This function will only work, if for the given Domain, the
        method Domain.getProtocols() has been called once. After calling
        this method the protocol classes are registered with it Plugin
        and Domain info.
        """
        # import pyworkflow.em as em
        # em.Domain.getProtocols()  # make sure the _package is set for each Protocol class
        # TODO: Check if we need to return scipion by default anymore
        # Now the basic EM protocols are defined by scipion-em (pwem)
        return getattr(cls, '_package', None)

    @classmethod
    def getClassPlugin(cls):
        package = cls.getClassPackage()
        return getattr(package, 'Plugin', None)

    @classmethod
    def getClassPackageName(cls):
        return cls.getClassPackage().__name__ if cls.getClassPackage() else "orphan"

    @classmethod
    def getClassDomain(cls):
        """ Return the Domain class where this Protocol class is defined. """
        return pw.Config.getDomain()

    @classmethod
    def getPluginLogoPath(cls):
        package = cls.getClassPackage()
        logo = getattr(package, '_logo', None)
        if logo:
            logoPath = (pw.findResource(logo) or
                        os.path.join(os.path.abspath(os.path.dirname(package.__file__)), logo))
        else:
            logoPath = None

        return logoPath

    @classmethod
    def validatePackageVersion(cls, varName, errors):
        """ Function to validate the the package version specified in
        configuration file ~/.config/scipion/scipion.conf is among the available
        options and it is properly installed.
        Params:
            package: the package object (ej: eman2 or relion). Package should contain the
                     following methods: getVersion(), getSupportedVersions()
            varName: the expected environment var containing the path (and version)
            errors: list to added error if found
        """
        package = cls.getClassPackage()
        packageName = cls.getClassPackageName()
        varValue = package.Plugin.getVar(varName)
        versions = ','.join(package.Plugin.getSupportedVersions())

        errorMsg = None

        if not package.Plugin.getActiveVersion():
            errors.append("We could not detect *%s* version. " % packageName)
            errorMsg = "The path value should contains a valid version (%s)." % versions
        elif not os.path.exists(varValue):
            errors.append("Path of %s does not exists." % varName)
            errorMsg = "Check installed packages and versions with command:\n "
            errorMsg += "*scipion install --help*"

        if errorMsg:
            errors.append("%s = %s" % (varName, varValue))
            errors.append(
                "Please, modify %s value in the configuration file:" % varName)
            errors.append("*~/.config/scipion/scipion.conf*")
            errors.append(errorMsg)
            errors.append("After fixed, you NEED TO RESTART THE PROJECT WINDOW")

    @classmethod
    def getClassLabel(cls, prependPackageName=True):
        """ Return a more readable string representing the protocol class """
        label = cls.__dict__.get('_label', cls.__name__)
        if prependPackageName:
            label = "%s - %s" % (cls.getClassPackageName(), label)
        return label

    @classmethod
    def isDisabled(cls):
        """ Return True if this Protocol is disabled.
        Disabled protocols will not be offered in the available protocols."""
        return False

    @classmethod
    def isBase(cls):
        """ Return True if this Protocol is a base class.
        Base classes should be marked with _label = None.
        """
        return cls.__dict__.get('_label', None) is None

    def getSubmitDict(self):
        """ Return a dictionary with the necessary keys to
        launch the job to a queue system.
        """
        queueName, queueParams = self.getQueueParams()
        hc = self.getHostConfig()

        script = self._getLogsPath(hc.getSubmitPrefix() + self.strId() + '.job')
        d = {'JOB_SCRIPT': script,
             'JOB_LOGS': self._getLogsPath(hc.getSubmitPrefix() + self.strId()),
             'JOB_NODEFILE': os.path.abspath(script.replace('.job', '.nodefile')),
             'JOB_NAME': self.strId(),
             'JOB_QUEUE': queueName,
             'JOB_NODES': self.numberOfMpi.get(),
             'JOB_THREADS': self.numberOfThreads.get(),
             'JOB_CORES': self.numberOfMpi.get() * self.numberOfThreads.get(),
             'JOB_HOURS': 72,
             'GPU_COUNT': len(self.getGpuList()),
             'QUEUE_FOR_JOBS': 'N'
             }
        d.update(queueParams)
        return d

    def useQueue(self):
        """ Return True if the protocol should be launched through a queue. """
        return self._useQueue.get()

    def useQueueForSteps(self):
        """ This function will return True if the protocol has been set
        to be launched through a queue by steps """
        return self.useQueue() and (self.getSubmitDict()["QUEUE_FOR_JOBS"] == "Y")

    def getQueueParams(self):
        if self._queueParams.hasValue():
            return json.loads(self._queueParams.get())
        else:
            return '', {}

    def hasQueueParams(self):
        return self._queueParams.hasValue()

    def setQueueParams(self, queueParams):
        self._queueParams.set(json.dumps(queueParams))

    @property
    def numberOfSteps(self):
        return self._numberOfSteps.get(0)

    @property
    def stepsDone(self):
        """ Return the number of steps executed. """
        return self._stepsDone.get(0)

    @property
    def cpuTime(self):
        """ Return the sum of all durations of the finished steps"""
        return self._cpuTime.get()

    def updateSteps(self):
        """ After the steps list is modified, this methods will update steps
        information. It will save the steps list and also the number of steps.
        """
        self._storeSteps()
        self._numberOfSteps.set(len(self._steps))
        self._store(self._numberOfSteps)

    def getStatusMessage(self):
        """ Return the status string and if running the steps done.
        """
        msg = self.getStatus()
        if self.isRunning() or self.isAborted() or self.isFailed():
            msg += " (done %d/%d)" % (self.stepsDone, self.numberOfSteps)

        return msg

    def getRunMode(self):
        """ Return the mode of execution, either:
        MODE_RESTART or MODE_RESUME. """
        return self.runMode.get()

    def hasSummaryWarnings(self):
        return len(self.summaryWarnings) != 0

    def addSummaryWarning(self, warningDescription):
        """Appends the warningDescription param to the list of summaryWarnings.
        Will be printed in the protocol summary."""
        self.summaryWarnings.append(warningDescription)
        return self.summaryWarnings

    def checkSummaryWarnings(self):
        """ Checks for warnings that we want to tell the user about by adding a
        warning sign to the run box and a description to the run summary.
        List of warnings checked:
        1. If the folder for this protocol run exists.
        """
        if not self.isSaved() and not os.path.exists(self.workingDir.get()):
            self.addSummaryWarning("*Missing run data*: The directory for this "
                                   "run is missing, so it won't be possible to "
                                   "use its outputs in other protocols.")

    def isContinued(self):
        """ Return if running in continue mode (MODE_RESUME). """
        return self.getRunMode() == MODE_RESUME

    # Methods that should be implemented in subclasses
    def _validate(self):
        """ This function can be overwritten by subclasses.
        Used from the public validate function.
        """
        return []

    @classmethod
    def getUrl(cls):
        return cls.getClassPlugin().getUrl(cls)

    @classmethod
    def isInstalled(cls):
        # We a consider a protocol installed if there are not errors
        # from the _validateInstallation function
        return not cls.validateInstallation()

    @classmethod
    def validateInstallation(cls):
        """ Check if the installation of this protocol is correct.
        By default, we will check if the protocols' package provide a
        validateInstallation function and use it.
        Returning an empty list means that the installation is correct
        and there are not errors. If some errors are found, a list with
        the error messages will be returned.
        """
        try:
            validateFunc = getattr(cls.getClassPackage().Plugin,
                                   'validateInstallation', None)

            return validateFunc() if validateFunc is not None else []
        except Exception as e:
            msg = str(e)
            msg += (" %s installation couldn't be validated. Possible cause "
                    "could be a configuration issue. Try to run scipion "
                    "config." % cls.__name__)
            print(msg)
            return [msg]

    def validate(self):
        """ Check that input parameters are correct.
        Return a list with errors, if the list is empty, all was ok.
        """
        errors = []
        # Validate that all input pointer parameters have a value
        for paramName, param in self.getDefinition().iterParams():
            # Get all self attribute that are pointers
            attr = getattr(self, paramName)
            paramErrors = []
            condition = self.evalParamCondition(paramName)
            if attr.isPointer():
                obj = attr.get()
                if condition and obj is None and not param.allowsNull:
                    paramErrors.append('cannot be EMPTY.')
            elif isinstance(attr, PointerList):
                # In this case allowsNull refers to not allowing empty items
                if not param.allowsNull:
                    if len(attr) == 0:
                        paramErrors.append('cannot be EMPTY.')
                    # Consider empty pointers
                    else:
                        if any(pointer.get() is None for pointer in attr):
                            paramErrors.append('Can not have EMPTY items.')

            else:
                if condition:
                    paramErrors = param.validate(attr.get())
            label = param.label.get()
            errors += ['*%s* %s' % (label, err) for err in paramErrors]

        try:
            # Check that all ids specified in the 'Wait for' form entry
            # are valid protocol ids
            proj = self.getProject()
            for protId in self.getPrerequisites():
                try:
                    prot = proj.getProtocol(int(protId))
                except Exception:
                    prot = None
                if prot is None:
                    errors.append('*%s* is not a valid protocol id.' % protId)

            # Validate specific for the subclass
            installErrors = self.validateInstallation()
            if installErrors:
                errors += installErrors
            childErrors = self._validate()
            if childErrors:
                errors += childErrors
        except Exception:
            import urllib
            exceptionStr = pwutils.formatExceptionInfo()
            errors.append("Protocol validation failed. It usually happens because there are some "
                          "input missing. Please check if the error message gives you any "
                          "hint:\n{}".format(exceptionStr))
        return errors

    def _warnings(self):
        """ Should be implemented in subclasses. See warning. """
        return []

    def warnings(self):
        """ Return some message warnings that can be errors.
        User should approve to execute a protocol with warnings. """
        return self._warnings()

    def _summary(self):
        """ Should be implemented in subclasses. See summary. """
        return ["No summary information."]

    def summary(self):
        """ Return a summary message to provide some information to users. """
        try:
            baseSummary = self._summary() or ['No summary information.']

            if isinstance(baseSummary, str):
                baseSummary = [baseSummary]

            if not isinstance(baseSummary, list):
                raise Exception("Developers error: _summary() is not returning "
                                "a list")

            comments = self.getObjComment()
            if comments:
                baseSummary += ['', '*COMMENTS:* ', comments]

            if self.getError().hasValue():
                baseSummary += ['', '*ERROR:*', self.getError().get()]

            if self.summaryWarnings:
                baseSummary += ['', '*WARNINGS:*']
                baseSummary += self.summaryWarnings

        except Exception as ex:
            baseSummary = [str(ex)]

        return baseSummary

    def getFileTag(self, fn):
        return "[[%s]]" % fn

    def getObjectTag(self, objName):
        if isinstance(objName, str):
            obj = getattr(self, objName, None)
        else:
            obj = objName

        if obj is None:
            return '*None*'

        if obj.isPointer():
            obj = obj.get()  # get the pointed object
            if obj is None:
                return '*None*'

        return "[[sci-open:%s][%s]]" % (obj.getObjId(), obj.getNameId())

    def _citations(self):
        """ Should be implemented in subclasses. See citations. """
        return getattr(self, "_references", [])

    def __getPluginBibTex(self):
        """ Return the _bibtex from the package """
        return getattr(self.getClassPackage(), "_bibtex", {})

    def _getCite(self, citeStr):
        bibtex = self.__getPluginBibTex()
        if citeStr in bibtex:
            text = self._getCiteText(bibtex[citeStr])
        else:
            text = "Reference with key *%s* not found." % citeStr
        return text

    def _getCiteText(self, cite, useKeyLabel=False):
        try:

            journal = cite.get("journal", cite.get("booktitle", ""))
            doi = cite.get("doi", "")
            # Get the first author surname
            if useKeyLabel:
                label = cite['ID']
            else:
                label = cite['author'].split(' and ')[0].split(',')[0].strip()
                label += ' et al., %s, %s' % (journal, cite['year'])
            if len(doi.strip()) > 0:
                text = '[[%s][%s]] ' % (doi.strip(), label)
            else:
                text = label.strip()
            return text

        except Exception as ex:
            print("Error with citation: " + label)
            print(ex)
            text = "Error with citation *%s*." % label
        return text

    def __getCitations(self, citations):
        """ From the list of citations keys, obtains the full
        info from the package _bibtex dict.
        """
        bibtex = self.__getPluginBibTex()
        newCitations = []
        for c in citations:
            if c in bibtex:
                newCitations.append(self._getCiteText(bibtex[c]))
            else:
                newCitations.append(c)
        return newCitations

    def __getCitationsDict(self, citationList, bibTexOutput=False):
        """ Return a dictionary with Cite keys and the citation links. """
        bibtex = self.__getPluginBibTex()
        od = OrderedDict()
        for c in citationList:
            if c in bibtex:
                if bibTexOutput:
                    od[c] = bibtex[c]
                else:
                    od[c] = self._getCiteText(bibtex[c])
            else:
                od[c] = c

        return od

    def getCitations(self, bibTexOutput=False):
        return self.__getCitationsDict(self._citations() or [],
                                       bibTexOutput=bibTexOutput)

    def getPackageCitations(self, bibTexOutput=False):
        refs = getattr(self.getClassPackage(), "_references", [])
        return self.__getCitationsDict(refs, bibTexOutput=bibTexOutput)

    def citations(self):
        """ Return a citation message to provide some information to users. """
        citations = list(self.getCitations().values())
        if citations:
            citations.insert(0, '*References:* ')

        packageCitations = self.getPackageCitations().values()
        if packageCitations:
            citations.append('*Package References:*')
            citations += packageCitations
        if not citations:
            return ['No references provided']
        return citations

    @classmethod
    def getHelpText(cls):
        """Get help text to show in the protocol help button"""
        helpText = cls.getDoc()
        # NOt used since getClassPlugin is always None
        # plugin = self.getClassPlugin()
        # if plugin:
        #     pluginMetadata = plugin.metadata
        #     helpText += "\n\nPlugin info:\n"
        #     for key, value in pluginMetadata.iteritems():
        #         helpText += "%s: \t%s\n" % (key, value)
        return helpText

    def _methods(self):
        """ Should be implemented in subclasses. See methods. """
        return ["No methods information."]

    def getParsedMethods(self):
        """ Get the _methods results and parse possible cites. """
        try:
            baseMethods = self._methods() or []
            bibtex = self.__getPluginBibTex()
            parsedMethods = []
            for m in baseMethods:
                for bibId, cite in bibtex.items():
                    k = '[%s]' % bibId
                    link = self._getCiteText(cite, useKeyLabel=True)
                    m = m.replace(k, link)
                parsedMethods.append(m)
        except Exception as ex:
            parsedMethods = ['ERROR generating methods info: %s' % ex]

        return parsedMethods

    def methods(self):
        """ Return a description about methods about current protocol
        execution. """
        # TODO: Maybe store the methods and not computing all times??
        return self.getParsedMethods() + [''] + self.citations()

    def runProtocol(self, protocol):
        """ Setup another protocol to be run from a workflow. """
        name = protocol.getClassName() + protocol.strId()
        # protocol.setName(name)
        protocol.setWorkingDir(self._getPath(name))
        protocol.setMapper(self.mapper)
        self.hostConfig.setStore(False)
        protocol.setHostConfig(self.getHostConfig())
        protocol.runMode.set(self._originalRunMode)
        protocol.makePathsAndClean()
        protocol.setStepsExecutor(self._stepsExecutor)
        protocol.run()
        self._store()  # TODO: check if this is needed

    def isChild(self):
        """ Return true if this protocol was invoked from a workflow
        (another protocol)"""
        return self.hasObjParentId()

    def getStepsGraph(self, refresh=True):
        """ Build a graph taking into account the dependencies between
        steps. In streaming we might find first the createOutputStep (e.g 24)
        depending on 25"""
        from pyworkflow.utils.graph import Graph
        g = Graph(rootName='PROTOCOL')
        root = g.getRoot()
        root.label = 'Protocol'

        steps = self.loadSteps()
        stepsDict = {str(i + 1): steps[i] for i in range(0, len(steps))}
        stepsDone = {}

        def addStep(i, step):

            # Exit if already done
            # This happens when, in streaming there is a child "before" a parent
            if i in stepsDone:
                return

            index = step.getIndex() or i
            sid = str(index)
            n = g.createNode(sid)
            n.step = step
            stepsDone[i] = n
            if step.getPrerequisites().isEmpty():
                root.addChild(n)
            else:
                for p in step.getPrerequisites():
                    # If prerequisite exists
                    if p not in stepsDone:
                        addStep(p, stepsDict[p])
                    stepsDone[p].addChild(n)

        for i, s in stepsDict.items():
            addStep(i, s)
        return g

    def closeMappers(self):
        """ Close the mappers of all output Sets. """
        for _, attr in self.iterOutputAttributes(Set):
            attr.close()

    def loadMappers(self):
        """ Open mapper connections from previous closed outputs. """
        for _, attr in self.iterOutputAttributes(Set):
            attr.load()

    def allowsDelete(self, obj):
        return False

    def legacyCheck(self):
        """ Hook defined to run some compatibility checks
        before display the protocol.
        """
        pass


class LegacyProtocol(Protocol):
    """ Special subclass of Protocol to be used when a protocol class
    is not found. It means that have been removed or it is in another
    development branch. In such, we will use the LegacyProtocol to
    simply store the parameters and inputs/outputs."""

    def __str__(self):
        return self.getObjLabel()

    # overload getClassDomain because legacy protocols
    # do not have a package associated to it
    @classmethod
    def getClassDomain(cls):
        return pw.Config.getDomain()


# ---------- Helper functions related to Protocols --------------------

def runProtocolMain(projectPath, protDbPath, protId):
    """ Main entry point when a protocol will be executed.
    This function should be called when:
    scipion runprotocol ...
    Params:
        projectPath: the absolute path to the project directory.
        protDbPath: path to protocol db relative to projectPath
        protId: id of the protocol object in db.
    """
    # Enter to the project directory and load protocol from db
    protocol = getProtocolFromDb(projectPath, protDbPath, protId, chdir=True)

    setDefaultLoggingContext(protId, protocol.getProject().getShortName())

    hostConfig = protocol.getHostConfig()

    # Create the steps executor
    executor = None
    nThreads = max(protocol.numberOfThreads.get(), 1)

    if protocol.stepsExecutionMode == STEPS_PARALLEL:
        if protocol.numberOfMpi > 1:
            # Handle special case to execute in parallel
            # We run "scipion run pyworkflow/...mpirun.py blah" instead of
            # calling directly "$SCIPION_PYTHON ...mpirun.py blah", so that
            # when it runs on a MPI node, it *always* has the scipion env.
            params = ['-m', 'scipion', 'runprotocol', pw.getPwProtMpiRunScript(),
                      projectPath, protDbPath, protId]
            # 'scipion' is treated now as an entry point, but if there is an alias with that name, the alias has higher
            # priority
            retcode = pwutils.runJob(None, pw.PYTHON, params,
                                     numberOfMpi=protocol.numberOfMpi.get(),
                                     hostConfig=hostConfig)
            sys.exit(retcode)

        elif nThreads > 1:
            if protocol.useQueueForSteps():
                executor = QueueStepExecutor(hostConfig,
                                             protocol.getSubmitDict(),
                                             nThreads - 1,
                                             gpuList=protocol.getGpuList())
            else:
                executor = ThreadStepExecutor(hostConfig, nThreads - 1,
                                              gpuList=protocol.getGpuList())

    if executor is None and protocol.useQueueForSteps():
        executor = QueueStepExecutor(hostConfig, protocol.getSubmitDict(), 1,
                                     gpuList=protocol.getGpuList())

    if executor is None:
        executor = StepExecutor(hostConfig,
                                gpuList=protocol.getGpuList())

    protocol.setStepsExecutor(executor)
    # Finally run the protocol
    protocol.run()


def runProtocolMainMPI(projectPath, protDbPath, protId, mpiComm):
    """ This function only should be called after enter in runProtocolMain
    and the proper MPI scripts have been started...so no validations
    will be made.
    """
    protocol = getProtocolFromDb(projectPath, protDbPath, protId, chdir=True)
    hostConfig = protocol.getHostConfig()
    # Create the steps executor
    executor = MPIStepExecutor(hostConfig, protocol.numberOfMpi.get() - 1,
                               mpiComm, gpuList=protocol.getGpuList())

    protocol.setStepsExecutor(executor)
    # Finally run the protocol
    protocol.run()


def getProtocolFromDb(projectPath, protDbPath, protId, chdir=False):
    """ Retrieve the Protocol object from a given .sqlite file
    and the protocol id.
    """

    if not os.path.exists(projectPath):
        raise Exception("ERROR: project path '%s' does not exist. "
                        % projectPath)

    fullDbPath = os.path.join(projectPath, protDbPath)

    if not os.path.exists(fullDbPath):
        raise Exception("ERROR: protocol database '%s' does not exist. "
                        % fullDbPath)

    # We need this import here because from Project is imported
    # all from protocol indirectly, so if move this to the top
    # we get an import error
    from pyworkflow.project import Project
    project = Project(pw.Config.getDomain(), projectPath)
    project.load(dbPath=os.path.join(projectPath, protDbPath), chdir=chdir,
                 loadAllConfig=False)
    protocol = project.getProtocol(protId)
    return protocol


def getUpdatedProtocol(protocol):
    """ Retrieve the updated protocol and close db connections
        """
    prot2 = getProtocolFromDb(protocol.getProject().path,
                              protocol.getDbPath(),
                              protocol.getObjId())
    # Close DB connections
    prot2.getProject().closeMapper()
    prot2.closeMappers()
    return prot2


def isProtocolUpToDate(protocol):
    """ Check timestamps between protocol lastModificationDate and the
    corresponding runs.db timestamp"""
    if protocol is None:
        return True

    if protocol.lastUpdateTimeStamp.get(None) is None:
        return False

    protTS = protocol.lastUpdateTimeStamp.datetime()

    if protTS is None:
        return False

    dbTS = pwutils.getFileLastModificationDate(protocol.getDbPath())

    if not (protTS and dbTS):
        print("Can't compare if protocol is up to date: "
              "Protocol %s, protocol time stamp: %s, %s timeStamp: %s"
              % (protocol, protTS, protocol, dbTS))
    else:
        return protTS >= dbTS


class ProtImportBase(Protocol):
    """ Base Import protocol"""
