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

import pyworkflow.tests as pwtests
import pyworkflow.mapper as pwmapper
import pyworkflow.protocol as pwprot


# TODO: this test seems not to be finished.
from pyworkflowtests.protocols import SleepingProtocol
from pyworkflowtests import Domain


class TestProtocolExecution(pwtests.BaseTest):
    
    @classmethod
    def setUpClass(cls):
        pwtests.setupTestOutput(cls)
    
    def test_StepExecutor(self):
        """Test the list with several Complex"""
        fn = self.getOutputPath("protocol.sqlite")
        print("Writing to db: %s" % fn)

        # Discover objects and protocols
        mapperDict = Domain.getMapperDict()

        # Check that the protocol has associated package
        mapper = pwmapper.SqliteMapper(fn, mapperDict)
        prot = SleepingProtocol(mapper=mapper, n=2,
                                workingDir=self.getOutputPath(''))
        domain = prot.getClassDomain()
        domain.printInfo()

        prot.setStepsExecutor(pwprot.StepExecutor(hostConfig=None))
        prot.run()
        mapper.commit()
        mapper.close()

        self.assertEqual(prot._steps[0].getStatus(), pwprot.STATUS_FINISHED)
        
        mapper2 = pwmapper.SqliteMapper(fn, mapperDict)
        prot2 = mapper2.selectById(prot.getObjId())
        
        self.assertEqual(prot.endTime.get(), prot2.endTime.get())
