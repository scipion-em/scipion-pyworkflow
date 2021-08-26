#!/usr/bin/env python
# **************************************************************************
# *
# * Authors:     J.M. de la Rosa Trevin (delarosatrevin@scilifelab.se) [1]
# *              Roberto Marabini       (roberto@cnb.csic.es) [2]
# *
# * [1] SciLifeLab, Stockholm University
# * [2] Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
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

import numpy as np
import time

from .tests import BaseTest
from pyworkflow.utils import TaskEngine, TaskGenerator, TaskProcessor


class TestThreading(BaseTest):
    def test_threads_processors(self):

        def generate():
            n = 10
            for i in range(1, n+1):
                mic = "mic_%03d.mrc" % i
                print("Created micrograph: %s" % mic)
                yield mic
                time.sleep(1)

        def filter(mic):
            print("Filtering micrograph: %s" % mic)
            time.sleep(3)
            return mic.replace(".mrc", "_filtered.mrc")

        def picking(mic):
            print("Picking micrograph: %s" % mic)
            time.sleep(2)
            m = 100
            xRand = np.random.randint(0, 1000, m)
            yRand = np.random.randint(0, 1000, m)
            coords = [(x, y) for x, y in zip(xRand, yRand)]
            time.sleep(1)
            return mic, coords

        te = TaskEngine(debug=False)

        g = te.addGenerator(generate,
                            name='GENERATOR')

        f1 = te.addProcessor(g.outputQueue, filter,
                             name='FILTER-1')
        f2 = te.addProcessor(g.outputQueue, filter,
                             name='FILTER-2',
                             outputQueue=f1.outputQueue)
        p = te.addProcessor(f1.outputQueue, picking,
                            name='PICKING')

        te.start()

        te.join()

        print("PROCESSING DONE!!!")


