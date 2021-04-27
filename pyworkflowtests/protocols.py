# -*- coding: utf-8 -*-
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
Definition of Mock protocols to be used within the tests in the Mock Domain
"""

import time
import datetime
import pyworkflow.utils as pwutils
import pyworkflow.object as pwobj
import pyworkflow.protocol as pwprot
from pyworkflowtests.objects import MockSetOfImages, MockImage

class SleepingProtocol(pwprot.Protocol):
    def __init__(self, **args):
        pwprot.Protocol.__init__(self, **args)
        self.name = pwobj.String(args.get('name', None))
        self.numberOfSleeps = pwobj.Integer(args.get('n', 1))
        self.runMode = pwobj.Integer(pwprot.MODE_RESUME)

    def sleepStep(self, t):
        log = self._getPath("step_%02d.txt" % t)
        f = open(log, 'w+')
        f.write("Going to sleep at %s\n"
                % pwutils.dateStr(datetime.datetime.now(), True))
        time.sleep(t)
        f.write("  Slept: %d seconds\n" % t)
        f.write("Awakened at %s\n"
                % pwutils.dateStr(datetime.datetime.now(), True))
        f.close()
        return [log]

    def _insertAllSteps(self):
        print("Inserting all steps...")
        for i in range(self.numberOfSleeps.get()):
            self._insertFunctionStep('sleepStep', i + 1)


class ParallelSleepingProtocol(SleepingProtocol):
    def _insertAllSteps(self):
        step1 = self._insertFunctionStep('sleepStep', 1)
        n = 2
        deps = [step1]
        for i in range(n):
            self._insertFunctionStep('sleepStep')

class ConcurrencyProtocol(SleepingProtocol):
    """ Protocol to test concurrency access to sets"""

    def __init__(self):
        super().__init__()
        self.stepsExecutionMode = pwprot.STEPS_PARALLEL

    def _defineParams(self, form):
        form.addParallelSection(threads=2, mpi=0)

    def _insertAllSteps(self):
        n = 2
        for i in range(n):
            self._insertFunctionStep('sleepAndOutput', 1, prerequisites=[])

    def sleepAndOutput(self, secs):
        self.sleepStep(secs)

        outputSet = self.getOutputSet("myOutput", MockSetOfImages)
        newImage = MockImage()
        with self._lock:
            outputSet.append(newImage)
            outputSet.write()
        self._store()


    def getOutputSet(self, attrName, setClass):
        output = getattr(self, attrName, None)

        if output is None:
            output = setClass.create(self._getExtraPath())
            self._defineOutputs(**{attrName: output})

        return output

class ProtOutputTest(pwprot.Protocol):
    """ Protocol to test scalar output and input linking"""
    _label = 'test output'

    def __init__(self, **args):
        pwprot.Protocol.__init__(self, **args)
        self.name = pwobj.String(args.get('name', None))

    def _defineParams(self, form):

        section = form.addSection("Input")
        section.addParam('iBoxSize', pwprot.IntParam, allowsPointers=True,
                         default=10,
                         label='Input box size as Integer',
                         validators=[pwprot.Positive])

        section.addParam('nullableInteger', pwprot.IntParam, allowsPointers=True,
                         label='Nullable Integer', allowsNull=True)

    def _createOutputStep(self):
        # New Output would be an Integer
        boxSize = pwobj.Integer(10)

        if self.iBoxSize.hasValue():
            boxSize.set(2*int(self.iBoxSize.get()))

        self._defineOutputs(oBoxSize=boxSize)

    def _insertAllSteps(self):
        self._insertFunctionStep('_createOutputStep')


class ProtMultiPointerTest(pwprot.Protocol):
    """ Class to test how multipointer params are exported to json"""
    def _defineParams(self, form):

        # This should cover Multipointer params that points to attributes...
        # therefore extended attribute of pointers should be used
        form.addParam('mpToAttr', pwprot.MultiPointerParam,
                      label="Multipointer to attribute",
                      pointerClass='String',
                      help="Should point to String inside another protocol")

        # This should cover Multipointer params that points to protocols...
        # therefore extended attribute of pointers should NOT be used
        form.addParam('mpToProts', pwprot.MultiPointerParam,
                      label="Multipointer to sets",
                      pointerClass='Protocol',
                      help="Should point to another protocol")
