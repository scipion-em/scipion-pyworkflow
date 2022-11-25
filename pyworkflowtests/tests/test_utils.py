#!/usr/bin/env python
# coding: latin-1
"""
Created on Mar 25, 2014

@author: airen
@author: roberto.marabini
"""


from subprocess import Popen
from io import StringIO

from pyworkflow import APPS
from pyworkflow.utils.process import killWithChilds
from pyworkflow.tests import *
from pyworkflow.utils import utils, prettyDict, getListFromValues
from pyworkflow.utils import ProgressBar


class TestBibtex(BaseTest):
    """ Some minor tests to the bibtexparser library. """

    @classmethod
    def setUpClass(cls):
        setupTestOutput(cls)
        
    def test_Parsing(self):
        bibtex = """

@article{delaRosaTrevin2013,
title = "Xmipp 3.0: An improved software suite for image processing in electron microscopy ",
journal = "Journal of Structural Biology ",
volume = "184",
number = "2",
pages = "321 - 328",
year = "2013",
issn = "1047-8477",
doi = "http://dx.doi.org/10.1016/j.jsb.2013.09.015",
url = "http://www.sciencedirect.com/science/article/pii/S1047847713002566",
author = "J.M. de la Rosa-Trevín and J. Otón and R. Marabini and A. Zaldívar and J. Vargas and J.M. Carazo and C.O.S. Sorzano",
keywords = "Electron microscopy, Single particles analysis, Image processing, Software package "
}

@incollection{Sorzano2013,
title = "Semiautomatic, High-Throughput, High-Resolution Protocol for Three-Dimensional Reconstruction of Single Particles in Electron Microscopy",
booktitle = "Nanoimaging",
year = "2013",
isbn = "978-1-62703-136-3",
volume = "950",
series = "Methods in Molecular Biology",
editor = "Sousa, Alioscka A. and Kruhlak, Michael J.",
doi = "10.1007/978-1-62703-137-0_11",
url = "http://dx.doi.org/10.1007/978-1-62703-137-0_11",
publisher = "Humana Press",
keywords = "Single particle analysis; Electron microscopy; Image processing; 3D reconstruction; Workflows",
author = "Sorzano, CarlosOscar and Rosa Trevín, J.M. and Otón, J. and Vega, J.J. and Cuenca, J. and Zaldívar-Peraza, A. and Gómez-Blanco, J. and Vargas, J. and Quintana, A. and Marabini, Roberto and Carazo, JoséMaría",
pages = "171-193",
}
"""

        prettyDict(utils.parseBibTex(bibtex))


class TestProccess(BaseTest):
    """ Some tests for utils.process module. """

    @classmethod
    def setUpClass(cls):
        setupTestOutput(cls)
        
    def test_Process(self):
        prog = pw.join(APPS, 'pw_sleep.py')
        p = Popen('python %s 500' % prog, shell=True)
        print("pid: %s" % p.pid)
        time.sleep(5)
        killWithChilds(p.pid)


class TestGetListFromRangeString(BaseTest):

    def test_getListFromRangeString(self):
        inputStrings = ["1,5-8,10"        , "2,6,9-11"       , "2 5, 6-8"     , "1-4 8"]
        outputLists = [[1, 5, 6, 7, 8, 10], [2, 6, 9, 10, 11], [2, 5, 6, 7, 8], [1,2,3,4, 8]]

        for s, o in zip(inputStrings, outputLists):
            self.assertEqual(o, pwutils.getListFromRangeString(s))
            # Check that also works properly with spaces as delimiters
            s2 = s.replace(',', ' ')
            self.assertEqual(o, pwutils.getListFromRangeString(s2))


class TestListFromValues(unittest.TestCase):
    """ Tests list created from str"""

    def _callAndAssert(self, strValue, expected, length=None, caster=str):

        result = getListFromValues( strValue, length, caster)

        self.assertEqual(result, expected, "List from string does not work for %s" % strValue)

    def test_getListFromValues(self):
        """ Test numeric list definitions like:
            '1 1 2x2 4 4' -> ['1', '1', '2', '2', '4', '4']
            '2x3, 3x4, 1' -> ['3', '3', '4', '4', '4', '1']"
        """

        self._callAndAssert('1 1 2x2 4 4', ['1', '1', '2', '2', '4', '4'])
        self._callAndAssert('2x3, 3x4, 1',['3', '3', '4', '4', '4', '1'])
        self._callAndAssert('2,3,4,1', [2, 3, 4, 1], caster=int)
        self._callAndAssert('2 , 3 , 4 , 1', [2, 3, 4, 1], caster=int)
        self._callAndAssert('2,3.3,4', [2.0, 3.3, 4.0], caster=float)



class TestProgressBar(unittest.TestCase):

    def caller(self, total, step, fmt, resultGold):
        ti = time.time()
        result = StringIO()
        pb = ProgressBar(total=total, fmt=fmt, output=result,
                         extraArgs={'objectId': 33})

        pb.start()
        for i in range(total):
            if i % step == 0:
                pb.update(i+1)
        pb.finish()
        self.assertEqual(resultGold.strip(), result.getvalue().strip())
        result.close()
        tf = time.time()
        print("%d iterations in %f sec" % (total, tf - ti))

    def test_dot(self):
        total = 1000000
        step = 10000
        ratio = int(total/step)
        resultGold = '.' * (ratio+1)
        self.caller(total=total, step=step,
                    fmt=ProgressBar.DOT, resultGold=resultGold)

    def test_default(self):
        total = 3
        step = 1
        resultGold = ('\rProgress: [                                        ] '
                      '  0%\rProgress: [=============                         '
                      '  ]  33%\rProgress: [==========================        '
                      '      ]  66%\rProgress: [=============================='
                      '==========] 100%')
        self.caller(total=total, step=step,
                    fmt=ProgressBar.DEFAULT, resultGold=resultGold)

    def test_full(self):
        total = 3
        step = 1
        resultGold = ('\r[                                        ] 0/3 (  0%)'
                      ' 3 to go\r[=============                           ] '
                      '1/3 ( 33%) 2 to go\r[==========================      '
                      '        ] 2/3 ( 66%) 1 to go\r[======================'
                      '==================] 3/3 (100%) 0 to go')
        self.caller(total=total, step=step,
                    fmt=ProgressBar.FULL, resultGold=resultGold)

    def test_objectid(self):
        total = 3
        step = 1
        ratio = int(total/step)
        resultGold = ('\r[                                        ] 0/3 (  0%)'
                      ' (objectId=33)\r[=============                         '
                      '  ] 1/3 ( 33%) (objectId=33)\r[========================'
                      '==              ] 2/3 ( 66%) (objectId=33)\r[=========='
                      '==============================] 3/3 (100%) '
                      '(objectId=33)')
        self.caller(total=total, step=step,
                    fmt=ProgressBar.OBJID, resultGold=resultGold)

