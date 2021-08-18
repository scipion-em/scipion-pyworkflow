#!/usr/bin/env python

import logging
import unittest

from pyworkflow import Config
from pyworkflow.utils import (getLineInFile,
                              LoggingConfigurator, restoreStdoutAndErr)
from pyworkflow.tests import BaseTest, setupTestOutput
from pyworkflow.utils.process import runJob


class TestLogs(BaseTest):
    
    @classmethod
    def setUpClass(cls):
        setupTestOutput(cls)        

    def testSimpleFileLog(self):

        # Default generic configuration
        Config.SCIPION_LOG = self.getOutputPath("general.log")
        genLogFn = Config.SCIPION_LOG
        print("General log file at %s" % genLogFn)
        LoggingConfigurator.setupLogging()
        log1 = logging.getLogger('pyworkflow.test.log.test_scipion_log')

        def testMessage(message, msg_callback, file, shouldExist):

            if msg_callback:
                msg_callback(message)

            self.assertEqual(shouldExist, bool(getLineInFile(message, file)))

        testMessage("INFO to GEN", log1.info, genLogFn, True)
        testMessage("DEBUG missing in GEN", log1.debug, genLogFn, False)
        testMessage("WARNING in GEN", log1.warning, genLogFn, True)
        testMessage("ERROR in GEN", log1.error, genLogFn, True)

        # Protocol run logging configuration (this is propagating the messages,
        # so messages end un in general log too). This is to allow custom configurations to receive running protocol messages)
        logFn = self.getOutputPath('stdout.log')
        logErrFn = self.getOutputPath('stdErr.log')
        log2 = LoggingConfigurator.setUpProtocolRunLogging(logFn, logErrFn)

        fileInfoTest = 'INFO to FILE'
        testMessage(fileInfoTest, log2.info, logFn, True)
        testMessage(fileInfoTest, None, genLogFn, False)

        fileDebugMsg = "DEBUG does not reach FILE nor GEN"
        testMessage(fileDebugMsg, log2.debug, logFn, False)
        testMessage(fileDebugMsg, None, genLogFn, False)

        fileWarningTest = 'WARNING to FILE and not GEN'
        testMessage(fileWarningTest, log2.warning, logFn, True)
        testMessage(fileWarningTest, None, genLogFn, False)

        fileErrorTest = 'ERROR to FILE and not GEN'
        testMessage(fileErrorTest, log2.error, logFn, True)
        testMessage(fileErrorTest, None, genLogFn, False)

        # Test print goes to the log file (stdout is captured)
        printStdOut = "Print ends up in stdout FILE"
        print(printStdOut, flush=True)
        testMessage(printStdOut,None, logFn, True)

        subprocessOut = "subprocess output in stdout FILE"
        runJob(None,"echo", subprocessOut)
        testMessage(subprocessOut,None, logFn, True)

        restoreStdoutAndErr()

if __name__ == '__main__':
    unittest.main()
