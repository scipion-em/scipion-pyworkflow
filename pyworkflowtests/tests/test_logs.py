#!/usr/bin/env python

import logging
import unittest

from pyworkflow import Config
from pyworkflow.utils import (getLineInFile,
                              setupLogging, setUpProtocolRunLogging, restoreStdoutAndErr)
from pyworkflow.tests import BaseTest, setupTestOutput


# FIXME:Nacho
# Ok, Nacho and Airen, explain what you have to fix! :)

class TestLogs(BaseTest):
    
    @classmethod
    def setUpClass(cls):
        setupTestOutput(cls)        

    def testSimpleFileLog(self):

        # Default generic configuration
        Config.SCIPION_LOG = self.getOutputPath("general.log")
        genLogFn = Config.SCIPION_LOG
        setupLogging()
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
        logFn = self.getOutputPath('fileLog.log')
        logErrFn = self.getOutputPath('errLog.log')
        log2 = setUpProtocolRunLogging(logFn, logErrFn)

        fileInfoTest = 'INFO to FILE and GEN'
        testMessage(fileInfoTest, log2.info, logFn, True)
        testMessage(fileInfoTest, None, genLogFn, True)

        fileDebugMsg = "DEBUG to FILE and GEN"
        testMessage(fileDebugMsg, log2.debug, logFn, False)
        testMessage(fileDebugMsg, None, genLogFn, False)

        fileWarningTest = 'WARNING to FILE and GEN'
        testMessage(fileWarningTest, log2.warning, logFn, True)
        testMessage(fileWarningTest, None, genLogFn, True)

        fileErrorTest = 'ERROR to FILE and GEN'
        testMessage(fileErrorTest, log2.error, logFn, True)
        testMessage(fileErrorTest, None, genLogFn, True)

        restoreStdoutAndErr()

if __name__ == '__main__':
    unittest.main()
