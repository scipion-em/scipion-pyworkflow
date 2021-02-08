# **************************************************************************
# *
# * Authors:     Pablo Conesa (pconesa@cnb.csic.es) [1]
# *              J.M. De la Rosa Trevin (delarosatrevin@scilifelab.se) [2]
# *
# * [1] Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# * [2] SciLifeLab, Stockholm University
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

import pyworkflow as pw
import pyworkflow.object as pwobj
import pyworkflow.tests as pwtests
import pyworkflow.mapper as pwmapper
import pyworkflow.protocol as pwprot
from pyworkflowtests.protocols import ProtOutputTest
from pyworkflowtests import Domain, MockObject


# Protocol to output of basic scipion objects
class TestProtocolOutputs(pwtests.BaseTest):
    @classmethod
    def setUpClass(cls):
        pwtests.setupTestProject(cls, writeLocalConfig=True)
        pwtests.setupTestOutput(cls)

        # Set the application domain
        pw.Config.setDomain("pyworkflowtests")

    def test_basicObjectOutput(self):
        """Test the list with several Complex"""
        fn = self.getOutputPath("protocol.sqlite")

        # Discover objects and protocols
        mapperDict = Domain.getMapperDict()

        mapper = pwmapper.SqliteMapper(fn, mapperDict)
        prot = ProtOutputTest(mapper=mapper, n=2,
                              workingDir=self.getOutputPath(''))

        # Add and old style o, not in the outputs dictionary
        prot.output1 = MockObject()

        self.assertFalse(prot._useOutputList.get(),
                         "useOutputList wrongly initialized")

        outputs = [o for o in prot.iterOutputAttributes()]
        self.assertTrue(1, len(outputs))

        prot._stepsExecutor = pwprot.StepExecutor(hostConfig=None)
        prot.run()

        self.assertEqual(prot._steps[0].getStatus(),
                         pwprot.STATUS_FINISHED)

        # Check there is an o
        self.assertOutput(prot)

        outputs = [o for o in prot.iterOutputAttributes()]

        # We are intentionally ignoring a protocol with o (EMObject)
        # That has been continued, We do not find a real case now.
        self.assertEqual(1, len(outputs),
                         msg="Integer o not registered properly.")

        outputs = [o for o in prot.iterOutputAttributes(pwobj.Integer)]

        # Test passing a filter
        self.assertEqual(1, len(outputs),
                         msg="Integer not matched when filtering outputs.")

        # Test with non existing class
        class NotRealClass:
            pass

        outputs = [o for o in prot.iterOutputAttributes(NotRealClass)]

        # Test passing a class
        self.assertEqual(0, len(outputs),
                         msg="Filter by class in iterOutputAttributes does "
                             "not work.")

        self.assertTrue(prot._useOutputList.get(),
                        "useOutputList not activated")

    def test_basicObjectInProject(self):
        prot = self.newProtocol(ProtOutputTest,
                                objLabel='to generate basic input')
        print("working dir: %s" % prot.getWorkingDir())
        # Define a negative output for later tests
        prot._defineOutputs(negative=pwobj.Integer(-20))
        self.launchProtocol(prot)

        # Default value is 10 so output is 20
        self.assertOutput(prot)

        # Second protocol to test linking
        prot2 = self.newProtocol(ProtOutputTest,
                                 objLabel='to read basic input')

        # Set the pointer for the integer
        prot2.iBoxSize.setPointer(pwobj.Pointer(prot, extended="oBoxSize"))
        self.launchProtocol(prot2)
        self.assertOutput(prot2, value=40)

        # Test validation: only positive numbers are allowed
        prot3 = self.newProtocol(ProtOutputTest,
                                 objLabel='invalid input',
                                 iBoxSize=-10)
        # We expect this to fail
        with self.assertRaises(Exception):
            self.launchProtocol(prot3)
        # Test validation: pointer value is validated
        prot4 = self.newProtocol(ProtOutputTest,
                                 objLabel='invalid pointer input')
        # Now use negative pointer output
        prot4.iBoxSize.setPointer(pwobj.Pointer(prot, extended="negative"))

        # We expect this to fail
        with self.assertRaises(Exception):
            self.launchProtocol(prot4)

    def assertOutput(self, prot, value=20):
        # Check there is an output
        self.assertTrue(hasattr(prot, 'oBoxSize'),
                        msg="Protocol output boxSize (OInteger) not registered"
                            " as attribute.")

        self.assertEqual(value, prot.oBoxSize.get(),
                         "oBoxSize value is wrong: %s , expected %s" %
                         (prot.oBoxSize, value))
