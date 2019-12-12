#!/usr/bin/env python
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
import pyworkflowtests.objects as objectsMod
from pyworkflowtests import Domain


class TestDomain(pwtests.BaseTest):

    def test_objects(self):
        """ Test that all objects are properly discovered. """
        objects = Domain.getObjects()
        for k in dir(objectsMod):
            v = getattr(objectsMod, k)
            if isinstance(v, objectsMod.MockObject):
                self.assertEqual(objects[k], v)

    def test_viewers(self):
        pass

    def test_wizards(self):
        pass
