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

from pyworkflow import Config
from pyworkflowtests.protocols import  ConcurrencyProtocol


class TestConcurrency(pwtests.BaseTest):
    
    @classmethod
    def setUpClass(cls):
        pwtests.setupTestOutput(cls)

    
       # Set the application domain
        Config.setDomain("pyworkflowtests")
        pwtests.setupTestProject(cls)


    def test_simple_steps_concurrency(self):
        prot = self.newProtocol(ConcurrencyProtocol, numberOfThreads=3)

        self.launchProtocol(prot)
