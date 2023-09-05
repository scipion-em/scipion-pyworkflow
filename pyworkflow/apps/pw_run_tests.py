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
Run or show the selected tests. Tests can be selected by giving
the "case", or by giving the paths and file pattern to use for
searching them.
"""
from pyworkflow.utils import LoggingConfigurator
import argparse
from collections import OrderedDict

import pyworkflow.tests as pwtests
from pyworkflow import getTestsScript, SCIPION_TESTS_CMD, Config

from pyworkflow.tests import *

MODULE = 0
CLASS = 1
TEST = 2


class Tester:
    def main(self, args=None):

        # Trigger plugin's variable definition
        Config.getDomain().getPlugins()

        parser = argparse.ArgumentParser(prog=self.getTestsCommand(), description=__doc__)
        g = parser.add_mutually_exclusive_group()
        g.add_argument('--run', action='store_true', help='run the selected tests')
        g.add_argument('--show', action='store_true', help='show available tests',
                       default=True)

        add = parser.add_argument  # shortcut

        add('--pattern', default='test*.py',
            help='pattern for the files that will be used in the tests')
        add('--grep', default=None, nargs='+',
            help='only show/run tests containing the provided words')
        add('--skip', default=None, nargs='+',
            help='skip tests that contains these words')
        add('--log', default=None, nargs='?',
            help="Generate logs files with the output of each test.")
        add('--mode', default='classes', choices=['modules', 'classes', 'onlyclasses', 'all'],
            help='how much detail to give in show mode')
        add('tests', metavar='TEST', nargs='*',
            help='test case from string identifier (module, class or callable)')
        args = parser.parse_args(args)

        if not args.run and not args.show and not args.tests:
            sys.exit(parser.format_help())

        # Logging stuff first
        self.log = args.log

        if self.log:
            LoggingConfigurator.setupLogging(logFile=self.log)
        else:
            logging.basicConfig(level=Config.SCIPION_LOG_LEVEL, format=Config.SCIPION_LOG_FORMAT)

        self.logger = logging.getLogger(__name__)

        # This goes intentionally to the output. Is not a logging line._S
        print("Running tests....")

        testsDict = OrderedDict()
        testLoader = unittest.defaultTestLoader

        if args.tests:
            # In this case the tests are passed as argument.
            # The full name of the test will be used to load it.
            testsDict['tests'] = unittest.TestSuite()
            for t in args.tests:
                try:
                    testsDict['tests'].addTests(testLoader.loadTestsFromName(t))
                except Exception as e:
                    self.logger.error('Cannot load test %s -- skipping' % t, exc_info=True)
        else:
            # In this other case, we will load the test available
            # from pyworkflow and the other plugins
            # self.paths = [('pyworkflow', os.path.dirname(os.path.dirname(pw.__file__)))]
            self.paths = []
            for name, plugin in pw.Config.getDomain().getPlugins().items():
                self.paths.append((name, os.path.dirname(plugin.__path__[0])))
            for k, p in self.paths:
                testPath = os.path.join(p, k, 'tests')
                if os.path.exists(testPath):
                    self.logger.debug("Discovering tests at %s" % testPath)
                    testsDict[k] = testLoader.discover(testPath,
                                                       pattern=args.pattern,
                                                       top_level_dir=p)

        self.grep = [g.lower() for g in args.grep] if args.grep else []
        self.skip = args.skip
        self.mode = args.mode

        if args.tests:
            self.runSingleTest(testsDict['tests'])

        elif args.run:
            for moduleName, tests in testsDict.items():
                self.logger.info(pwutils.cyanStr(">>>> %s" % moduleName))
                self.runTests(moduleName, tests)

        elif args.grep:
            pattern = args.grep[0]
            for moduleName, tests in testsDict.items():
                self.printTests(pattern, tests)

        else:
            for moduleName, tests in testsDict.items():
                if self._match(moduleName):
                    print(pwutils.cyanStr(">>>> %s" % moduleName))
                    self.printTests(moduleName, tests)

    def _match(self, itemName):
        itemLower = itemName.lower()
        grep = (not self.grep or
                all(g.lower() in itemLower for g in self.grep))
        skip = (self.skip and
                any(g.lower() in itemLower for g in self.skip))

        return grep and not skip

    def __iterTests(self, test):
        """ Recursively iterate over a testsuite. """
        self.logger.debug("__iterTests: %s, is-suite: %s" % (str(test.__class__),
                                                 isinstance(test, unittest.TestSuite)))

        if isinstance(test, unittest.TestSuite):
            for t in test:
                self.__iterTests(t)
        else:
            yield test

    def _visitTests(self, moduleName, tests, newItemCallback):
        """ Show the list of tests available """
        mode = self.mode

        assert mode in ['modules', 'classes', 'onlyclasses', 'all'], 'Unknown mode %s' % mode

        # First flatten the list of tests.
        # testsFlat = list(iter(self.__iterTests(tests)))

        testsFlat = []
        toCheck = [t for t in tests]

        while toCheck:
            test = toCheck.pop()
            if isinstance(test, unittest.TestSuite):
                toCheck += [t for t in test]
            elif test not in testsFlat:
                testsFlat.append(test)

        # Follow the flattened list of tests and show the module, class
        # and name, in a nice way.
        lastClass = None
        lastModule = None
        if testsFlat:
            for t in testsFlat:

                testModuleName, className, testName = t.id().rsplit('.', 2)

                # If there is a failure loading the test, show it
                errorStr = 'unittest.loader._FailedTest.'
                if testModuleName.startswith(errorStr):
                    newName = t.id().replace(errorStr, '')
                    if self._match(newName):
                        self.logger.error(
                            pwutils.redStr('Error loading the test. Please, run the test for more information: ' + newName))
                    continue

                if testModuleName != lastModule:
                    lastModule = testModuleName
                    if mode != 'onlyclasses':
                        newItemCallback(MODULE, "%s" % testModuleName)

                if mode in ['classes', 'onlyclasses', 'all'] and className != lastClass:
                    lastClass = className
                    newItemCallback(CLASS, "%s.%s"
                                    % (testModuleName, className))

                if mode == 'all':
                    newItemCallback(TEST, "%s.%s.%s"
                                    % (testModuleName, className, testName))
        else:
            if not self.grep:
                self.logger.warning(pwutils.greenStr(' The plugin does not have any test'))

    def _printNewItem(self, itemType, itemName):
        if self._match(itemName):
            spaces = (itemType * 2) * ' '
            # Do not use intentionally the logger. This is not a logging output but a GUI output
            print("%s %s %s" % (spaces, self.getTestsCommand(), itemName))

    def getTestsCommand(self):
        return os.environ.get(SCIPION_TESTS_CMD, getTestsScript())

    def printTests(self, moduleName, tests):
        self._visitTests(moduleName, tests, self._printNewItem)

    def _runNewItem(self, itemType, itemName):
        if self._match(itemName):
            spaces = (itemType * 2) * ' '
            script = getTestsScript()
            cmd = "%s %s %s %s" % (pw.PYTHON, script, spaces, itemName)
            run = ((itemType == MODULE and self.mode == 'modules') or
                   (itemType == CLASS and self.mode in ('classes', 'onlyclasses')) or
                   (itemType == TEST and self.mode == 'all'))
            if run:
                if self.log:
                    # logFile = join(self.testsDir, '%s.txt' % itemName)
                    cmdFull = cmd + " >> %s 2>&1" % self.log
                else:
                    logFile = ''
                    cmdFull = cmd

                self.logger.info(pwutils.greenStr(cmdFull))
                t = pwutils.Timer()
                t.tic()
                self.testCount += 1
                os.system(cmdFull)

    def runTests(self, moduleName, tests):

        self.testCount = 0
        self._visitTests(moduleName, tests, self._runNewItem)

    def runSingleTest(self, tests):
        result = pwtests.GTestResult()
        tests.run(result)
        result.doReport()
        resultPassed = result.numberTests - result.testFailed
        sys.exit(1 if result.testFailed > 0 or resultPassed == 0 else 0)


if __name__ == '__main__':
    Tester().main()
