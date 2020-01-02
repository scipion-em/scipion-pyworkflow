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

import pyworkflow.utils as pwutils
import pyworkflow.object as pwobj
import pyworkflow.protocol as pwprot


class SleepingProtocol(pwprot.Protocol):
    def __init__(self, **args):
        pwprot.Protocol.__init__(self, **args)
        self.name = pwobj.String(args.get('name', None))
        self.numberOfSleeps = pwobj.Integer(args.get('n', 1))
        self.runMode = pwobj.Integer(pwprot.MODE_RESUME)

    def sleepStep(self, t, s):
        log = self._getPath("step_%02d.txt" % t)
        import time
        import datetime
        f = open(log, 'w+')
        f.write("Going to sleep at %s\n"
                % pwutils.dateStr(datetime.datetime.now(), True))
        time.sleep(t)
        f.write("  Slept: %d seconds\n" % t)
        f.write("Awaked at %s\n"
                % pwutils.dateStr(datetime.datetime.now(), True))
        f.close()
        return [log]

    def _insertAllSteps(self):
        print("Inserting all steps...")
        for i in range(self.numberOfSleeps.get()):
            self._insertFunctionStep('sleepStep', i + 1, 'sleeping %d' % i)


class ParallelSleepingProtocol(SleepingProtocol):
    def _insertAllSteps(self):
        step1 = self._insertFunctionStep('sleepStep', 1, '1')
        n = 2
        deps = [step1]
        for i in range(n):
            self._insertFunctionStep('sleepStep')


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
