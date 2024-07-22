import logging
logger = logging.getLogger(__name__)

import sys
import os
import time
from traceback import format_exception
import unittest
from os.path import join, relpath

import pyworkflow as pw
import pyworkflow.utils as pwutils
from pyworkflow.project import Manager
from pyworkflow.protocol import MODE_RESTART, getProtocolFromDb
from pyworkflow.object import Set

SMALL = 'small'
PULL_REQUEST = 'pull'
DAILY = 'daily'
WEEKLY = 'weekly'

# Type hint when creating protocols
from typing import TypeVar
T = TypeVar('T')

# Procedure to check if a test class has an attribute called _labels and if so
# then it checks if the class test matches any of the labels in input label parameter.
def hasLabel(TestClass, labels):
    # Get _labels attributes in class if any.
    classLabels = getattr(TestClass, '_labels', None)

    # Check if no label in test class.    
    return classLabels is not None and any(l in classLabels for l in labels)


class DataSet:
    _datasetDict = {}  # store all created datasets

    def __init__(self, name, folder, files, url=None):
        """ 
        Params:
            
        #filesDict is dict with key, value pairs for each file
        """
        self._datasetDict[name] = self
        self.folder = folder
        self.path = join(pw.Config.SCIPION_TESTS, folder)
        self.filesDict = files
        self.url = url

    def getFile(self, key):
        if key in self.filesDict:
            return join(self.path, self.filesDict[key])
        return join(self.path, key)

    def getPath(self):
        return self.path

    @classmethod
    def getDataSet(cls, name):
        """
        This method is called every time the dataset want to be retrieved
        """
        assert name in cls._datasetDict, "Dataset: %s dataset doesn't exist." % name

        ds = cls._datasetDict[name]
        folder = ds.folder
        url = '' if ds.url is None else ' -u ' + ds.url

        if not pw.Config.SCIPION_TEST_NOSYNC:
            command = ("%s %s --download %s %s"
                       % (pw.PYTHON, pw.getSyncDataScript(), folder, url))
            logger.info(">>>> %s" % command)
            os.system(command)

        return cls._datasetDict[name]


class BaseTest(unittest.TestCase):
    _labels = [WEEKLY]

    @classmethod
    def getOutputPath(cls, *filenames):
        """Return the path to the SCIPION_HOME/tests/output dir
        joined with filename"""
        return join(cls.outputPath, *filenames)

    @classmethod
    def getRelPath(cls, basedir, filename):
        """Return the path relative to SCIPION_HOME/tests"""
        return relpath(filename, basedir)

    @classmethod
    def launchProtocol(cls, prot, **kwargs):
        """ Launch a given protocol using cls.proj.

        :param wait: if True the function will return after the protocol runs.
            If not specified, then if waitForOutput is passed, wait is false.
        :param waitForOutputs: a list of expected outputs, ignored if wait=True

        """
        wait = kwargs.get('wait', None)
        waitForOutputs = kwargs.get('waitForOutput', [])

        if wait is None:
            wait = not waitForOutputs

        if getattr(prot, '_run', True):
            cls.proj.launchProtocol(prot, wait=wait)
            if not wait and waitForOutputs:
                while True:
                    time.sleep(10)
                    prot = cls.updateProtocol(prot)
                    if all(prot.hasAttribute(o) for o in waitForOutputs):
                        return prot

        if prot.isFailed():

            cls.printLastLogLines(prot)
            raise Exception("Protocol %s execution failed. See last log lines above for more details." % prot.getRunName())

        if not prot.isFinished() and not prot.useQueue():  # when queued is not finished yet

            cls.printLastLogLines(prot)
            raise Exception("Protocol %s didn't finish. See last log lines above for more details." % prot.getRunName())

        return prot

    @staticmethod
    def printLastLogLines(prot):
        """ Prints the last log lines (50 or  'PROT_LOGS_LAST_LINES' env variable) from stdout and stderr log files

        :param prot: Protocol to take the logs from

        """
        logs = {"STD OUT": 0, "STD ERR":1}

        lastLines = int(os.environ.get('PROT_LOGS_LAST_LINES', 50))

        # For each log file to print
        for key in logs:

            logger.info(pwutils.cyanStr("\n*************** last %s lines of %s *********************\n" % (lastLines, key)))
            logLines = prot.getLogsLastLines(lastLines, logFile=logs[key])
            for i in range(0, len(logLines)):
                logger.info(logLines[i])
            logger.info(pwutils.cyanStr("\n*************** end of %s *********************\n" % key))

            sys.stdout.flush()

    @classmethod
    def saveProtocol(cls, prot):
        """ Saves a protocol using cls.proj """
        cls.proj.saveProtocol(prot)

    @classmethod
    def _waitOutput(cls, prot, outputAttributeName, sleepTime=20, timeOut=5000):
        """ Wait until the output is being generated by the protocol. """

        def _loadProt():
            # Load the last version of the protocol from its own database
            loadedProt = getProtocolFromDb(prot.getProject().path,
                                           prot.getDbPath(),
                                           prot.getObjId())
            # Close DB connections
            loadedProt.getProject().closeMapper()
            loadedProt.closeMappers()
            return loadedProt

        counter = 1
        prot2 = _loadProt()

        numberOfSleeps = timeOut/sleepTime

        while (not prot2.hasAttribute(outputAttributeName)) and prot2.isActive():
            time.sleep(sleepTime)
            prot2 = _loadProt()
            if counter > numberOfSleeps:
                logger.warning("Timeout (%s) reached waiting for %s at %s" % (timeOut, outputAttributeName, prot))
                break
            counter += 1

        # Update the protocol instance to get latest changes
        cls.proj._updateProtocol(prot)

    @classmethod
    def newProtocol(cls, protocolClass:T, **kwargs)->T:
        """ Create new protocols instances through the project
        and return a newly created protocol of the given class
        """
        # Try to continue from previous execution
        if pwutils.envVarOn('SCIPION_TEST_CONTINUE'):
            candidates = cls.proj.mapper.selectByClass(protocolClass.__name__)
            if candidates:
                c = candidates[0]
                if c.isFinished():
                    setattr(c, '_run', False)
                else:
                    c.runMode.set(MODE_RESTART)
                return c
        return cls.proj.newProtocol(protocolClass, **kwargs)

    @classmethod
    def compareSets(cls, test, set1, set2):
        """ Iterate the elements of both sets and check
        that all elements have equal attributes. """
        for item1, item2 in zip(set1, set2):
            areEqual = item1.equalAttributes(item2)
            if not areEqual:
                logger.info("item 1 and item2 are different: ")
                item1.printAll()
                item2.printAll()
            test.assertTrue(areEqual)

    def compareSetProperties(self, set1:Set, set2:Set, ignore = ["_size", "_mapperPath"]):
        """ Compares 2 sets' properties"""

        self.assertTrue(set1.equalAttributes(set2, ignore=ignore, verbose=True), "Set1 (%s) properties differs from set2 (%s)." % (set1, set2))
        self.assertTrue(set2.equalAttributes(set1, ignore=ignore, verbose=True), 'Set2 (%s) has properties that set1 (%s) does not have.' % (set2, set1))

    def assertSetSize(self, setObject, size=None, msg=None, diffDelta=None):
        """ Check if a pyworkflow Set is not None nor is empty, or of a determined size or
        of a determined size with a percentage (base 1) of difference"""
        self.assertIsNotNone(setObject, msg)
        setObjSize = setObject.getSize()

        if size is None:
            # Test is not empty
            self.assertNotEqual(setObjSize, 0, msg)
        else:
            if diffDelta:
                self.assertLessEqual(abs(setObjSize - size), round(diffDelta * size), msg)
            else:
                self.assertEqual(setObjSize, size, msg)

    def assertIsNotEmpty(self, setObject, msg=None):
        """ Check if the pyworkflow object is not None nor is empty"""
        self.assertIsNotNone(setObject, msg)

        self.assertIsNotNone(setObject.get(), msg)

    @classmethod
    def setupTestOutput(cls):
        setupTestOutput(cls)


def setupTestOutput(cls):
    """ Create the output folder for a give Test class. """
    cls.outputPath = join(pw.Config.SCIPION_TESTS_OUTPUT, cls.__name__)
    pwutils.cleanPath(cls.outputPath)
    pwutils.makePath(cls.outputPath)


def setupTestProject(cls, writeLocalConfig=False):
    """ Create and setup a Project for a give Test class. """
    projName = cls.__name__
    hostsConfig = None

    if writeLocalConfig:
        hostsConfig = '/tmp/hosts.conf'
        logger.info("Writing local config: %s" % hostsConfig)
        import pyworkflow.protocol as pwprot
        pwprot.HostConfig.writeBasic(hostsConfig)

    if os.environ.get('SCIPION_TEST_CONTINUE', None) == '1':
        proj = Manager().loadProject(projName)
    else:
        proj = Manager().createProject(projName, hostsConf=hostsConfig)

    cls.outputPath = proj.path
    # Create project does not change the working directory anymore
    os.chdir(cls.outputPath)
    cls.projName = projName
    cls.proj = proj


class GTestResult(unittest.TestResult):
    """ Subclass TestResult to output tests results with colors
    (green for success and red for failure)
    and write a report on an .xml file. 
    """
    xml = None
    testFailed = 0
    numberTests = 0

    def __init__(self):
        unittest.TestResult.__init__(self)
        self.startTimeAll = time.time()

    def openXmlReport(self, classname, filename):
        pass

    def doReport(self):
        secs = time.time() - self.startTimeAll
        logger.info("\n%s run %d tests (%0.3f secs)\n" %
                         (pwutils.greenStr("[==========]"),
                          self.numberTests, secs))
        if self.testFailed:
            logger.info("%s %d tests\n"
                             % (pwutils.redStr("[  FAILED  ]"),
                                self.testFailed))
        logger.info("%s %d tests\n"
                         % (pwutils.greenStr("[  PASSED  ]"),
                            self.numberTests - self.testFailed))

    def tic(self):
        self.startTime = time.time()

    def toc(self):
        return time.time() - self.startTime

    def startTest(self, test):
        self.tic()
        self.numberTests += 1

    @staticmethod
    def getTestName(test):
        parts = str(test).split()
        name = parts[0]
        parts = parts[1].split('.')
        classname = parts[-1].replace(")", "")
        return "%s.%s" % (classname, name)

    def addSuccess(self, test):
        secs = self.toc()
        logger.info("%s %s (%0.3f secs)\n" %
                         (pwutils.greenStr('[ RUN   OK ]'),
                          self.getTestName(test), secs))

    def reportError(self, test, err):
        logger.info("%s %s\n" % (pwutils.redStr('[   FAILED ]'),
                                      self.getTestName(test)))
        logger.info("\n%s"
                         % pwutils.redStr("".join(format_exception(*err))))
        self.testFailed += 1

    def addError(self, test, err):
        self.reportError(test, err)

    def addFailure(self, test, err):
        self.reportError(test, err)
