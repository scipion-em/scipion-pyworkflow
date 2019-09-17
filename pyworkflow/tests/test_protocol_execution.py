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

from pyworkflow.object import *
from tests import *
from pyworkflow.mapper import SqliteMapper
from pyworkflow.utils import dateStr
from pyworkflow.protocol import Protocol
from pyworkflow.protocol.constants import MODE_RESUME, STATUS_FINISHED
from pyworkflow.protocol.executor import StepExecutor

import mock_domain as mod
import mock_domain.protocols as modprot


# TODO: this test seems not to be finished.
class TestProtocolExecution(BaseTest):
    
    @classmethod
    def setUpClass(cls):
        setupTestOutput(cls)
    
    def test_StepExecutor(self):
        """Test the list with several Complex"""
        fn = self.getOutputPath("protocol.sqlite")
        print("Writing to db: %s" % fn)

        mapper = SqliteMapper(fn, globals())
        prot = modprot.SleepingProtocol(mapper=mapper, n=2,
                                        workingDir=self.getOutputPath(''))

        # Discover objects and protocols
        mapperDict = globals()
        mapperDict.update(mod.Domain.getObjects())
        mapperDict.update(mod.Domain.getProtocols())

        # Check that the protocol has associated package
        package = prot.getClassPackage()
        package.Domain.printInfo()

        prot.setStepsExecutor(StepExecutor(hostConfig=None))
        prot.run()
        mapper.commit()
        mapper.close()

        self.assertEqual(prot._steps[0].getStatus(), STATUS_FINISHED)
        
        mapper2 = SqliteMapper(fn, mapperDict)
        prot2 = mapper2.selectById(prot.getObjId())
        
        self.assertEqual(prot.endTime.get(), prot2.endTime.get())
