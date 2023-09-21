#!/usr/bin/env python
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

import os
import datetime as dt
from logging import DEBUG, lastResort
from time import sleep

import pyworkflow.object as pwobj
import pyworkflow.tests as pwtests
from pyworkflow.mapper.sqlite import ID, CREATION
from ..objects import (Complex, MockSetOfImages, MockImage, MockObject,
                       MockAcquisition, MockMicrograph)

IMAGES_STK = "images.stk"

NUMERIC_ATRIBUTE_NAME = "1"

NUMERIC_ATTRIBUTE_VALUE = "numeric_attribute"


class ListContainer(pwobj.Object):
    def __init__(self, **args):
        pwobj.Object.__init__(self, **args)
        self.csv = pwobj.CsvList()
    
    
class TestObject(pwtests.BaseTest):
    @classmethod
    def setUpClass(cls):
        pwtests.setupTestOutput(cls)

    def test_ObjectsDict(self):
        # Validate that the object dict is populated correctly
        basicObjNames = [
            'Scalar', 'Integer', 'Float', 'String', 'Pointer', 'Boolean',
            'OrderedObject', 'List', 'CsvList', 'PointerList', 'Set'
        ]
        self.assertTrue(all(name in pwobj.OBJECTS_DICT
                            for name in basicObjNames))

    def test_Object(self):
        value = 2
        i = pwobj.Integer(value)
        self.assertEqual(value, i.get())
        # compare objects
        i2 = pwobj.Integer(value)
        self.assertEqual(i, i2)
        
        value = 2.
        f = pwobj.Float(value)
        self.assertAlmostEqual(value, f.get())
        
        f.multiply(5)
        self.assertAlmostEqual(value*5, f.get())
        
        a = pwobj.Integer()
        self.assertEqual(a.hasValue(), False)
        c = Complex.createComplex()
        # Check values are correct
        self.assertEqual(c.imag.get(), Complex.cGold.imag)
        self.assertEqual(c.real.get(), Complex.cGold.real)
        
        # Test Boolean logic
        b = pwobj.Boolean(False)
        self.assertTrue(not b.get())

        b.set('True')
        self.assertTrue(b.get())
        
        b = pwobj.Boolean()
        b.set(False)
        self.assertTrue(not b.get())
        
        # CsvList should be empty if set to ''
        l = pwobj.CsvList()
        l.set('')
        self.assertEqual(len(l), 0)

        # Test emptiness
        self.assertIsNotEmpty(b)

    def testWithPointer(self):

        obj = pwobj.Integer(10)

        self.assertFalse(obj.hasPointer(),
                         "Default instantiation off Integer has a pointer.")

        self.assertEqual(obj.get(), 10, "Integer.get(), without pointer fails.")

        pointee = pwobj.Object()
        setattr(pointee, "value", pwobj.Integer(20))

        # Set a pointer (not a real case though, but enough here)
        obj.setPointer(pwobj.Pointer(pointee, extended='value'))

        self.assertEqual(obj.get(), 20, "Integer.get() fails with a pointer.")

    def test_String(self):
        value = 'thisisastring'
        s = pwobj.String(value)
        self.assertEqual(value, s.get())
        self.assertEqual(s.hasValue(), True)
        
        s2 = pwobj.String()
        # None value is considered empty
        self.assertTrue(s2.empty(), "s2 string should be empty if None")
        s2.set(' ')
        # Only spaces is also empty
        self.assertTrue(s2.empty(), "s2 string should be empty if only spaces")
        s2.set('something')
        # No empty after some value
        self.assertFalse(s2.empty(),
                         "s2 string should not be empty after value")

        now = dt.datetime.now()
        s.set(now)
        self.assertEqual(now, s.datetime())

        # Ranges and values
        s2.set("1 2 3 4")
        self.assertEqual(s2.getListFromValues(caster=float), [1.,2.,3.,4.])
        self.assertEqual(s2.getListFromRange(), [1, 2, 3, 4])

        # Values ...
        s2.set("2x4, 4, 7")
        self.assertEqual(s2.getListFromValues(), [4, 4, 4, 7])

        # Ranges
        s2.set("2-8, 1-2, 7")
        self.assertEqual(s2.getListFromRange(), [2, 3, 4, 5, 6, 7, 8, 1, 2, 7])

    def test_Pointer(self):
        c = Complex.createComplex()
        p = pwobj.Pointer()
        p.set(c)
        p.setExtended('Name')
        c.Name = pwobj.String('Paquito')

        self.assertEqual(p.get(), 'Paquito')
        stackFn = IMAGES_STK
        mrcsFn = "images.mrcs"
        fn = self.getOutputPath('test_images.sqlite')
        imgSet = MockSetOfImages(filename=fn)
        imgSet.setSamplingRate(1.0)
        for i in range(10):
            img = MockImage()
            img.setLocation(i+1, stackFn)
            imgSet.append(img)

        imgSet.write()

        # Test that image number 7 is correctly retrieved
        # from the set
        img7 = imgSet[7]
        self.assertEqual(img7.getFileName(), stackFn)

        # Modify some properties of image 7 to test update
        img7.setFileName(mrcsFn)
        img7.setSamplingRate(2.0)
        imgSet.update(img7)
        # Write changes after the image 7 update
        imgSet.write()

        # Read again the set to be able to retrieve elements
        imgSet = MockSetOfImages(filename=fn)

        # Validate that image7 was properly updated
        img7 = imgSet[7]
        self.assertEqual(img7.getFileName(), mrcsFn)

        o = MockObject()

        o.pointer = pwobj.Pointer()
        o.pointer.set(imgSet)

        # This is not true anymore ans is allowed unless we see is needed
        # The main reason is a boost in performance.
        # o.refC = o.pointer.get()
        # attrNames = [k for k, a in o.getAttributes()]
        # # Check that 'refC' should not appear in attributes
        # # since it is only an "alias" to an existing pointed value
        # self.assertNotIn('refC', attrNames)

        self.assertFalse(o.pointer.hasExtended(),
                         'o.pointer should not have extended at this point')

        o.pointer.setExtended(7)

        self.assertTrue(o.pointer.hasExtended())
        self.assertTrue(o.pointer.hasExtended())
        self.assertEqual(o.pointer.getExtended(), "7")

        # Check that the Item 7 of the set is properly
        # retrieved by the pointer after setting the extended to 7
        self.assertEqual(imgSet[7], o.pointer.get())

        # Test the keyword arguments of Pointer constructor
        # repeat above tests with new pointer
        ptr = pwobj.Pointer(value=imgSet, extended=7)
        self.assertTrue(ptr.hasExtended())
        self.assertTrue(ptr.hasExtended())
        self.assertEqual(ptr.getExtended(), "7")

        # Check that the Item 7 of the set is properly
        # retrieved by the pointer after setting the extended to 7
        self.assertEqual(imgSet[7], ptr.get())

        o2 = pwobj.Object()
        o2.outputImages = imgSet
        ptr2 = pwobj.Pointer()
        ptr2.set(o2)
        # Test nested extended attributes
        ptr2.setExtended('outputImages.7')
        self.assertEqual(imgSet[7], ptr2.get())

        # Same as ptr2, but setting extended in constructor
        ptr3 = pwobj.Pointer(value=o2, extended='outputImages.7')
        self.assertEqual(imgSet[7], ptr3.get())

        # Test copy between pointer objects
        ptr4 = pwobj.Pointer()
        ptr4.copy(ptr3)
        self.assertEqual(imgSet[7], ptr4.get())
        self.assertEqual(ptr4.getExtended(), 'outputImages.7')

        # Test numeric attributes.
        setattr(o2, NUMERIC_ATRIBUTE_NAME, NUMERIC_ATTRIBUTE_VALUE)
        ptr5 = pwobj.Pointer(value=o2, extended=NUMERIC_ATRIBUTE_NAME)
        self.assertEqual(NUMERIC_ATTRIBUTE_VALUE, ptr5.get())

    def test_Sets(self):
        stackFn = IMAGES_STK
        fn = self.getOutputPath('test_images2.sqlite')

        imgSet = MockSetOfImages(filename=fn)

        halfTimeStamp = None

        for i in range(10):
            img = MockImage()
            img.setLocation(i + 1, stackFn)
            img.setSamplingRate(i % 3)
            imgSet.append(img)
            if i == 4:
                sleep(1)
                halfTimeStamp = dt.datetime.utcnow().replace(microsecond=0)
        imgSet.write()

        # Test size is 10
        self.assertSetSize(imgSet, 10)

        # Test hasChangedSince
        timeStamp = dt.datetime.now()
        self.assertFalse(imgSet.hasChangedSince(timeStamp), "Set.hasChangedSince returns true when it hasn't changed.")
        # Remove 10 seconds
        self.assertTrue(imgSet.hasChangedSince(timeStamp-dt.timedelta(0,10)), "Set.hasChangedSince returns false when it has changed.")

        # PERFORMANCE functionality
        def checkSetIteration(limit, skipRows=None):

            expectedId = 1 if skipRows is None else skipRows+1
            index = 0
            for item in imgSet.iterItems(limit=(limit, skipRows)):
                self.assertEqual(item.getIndex(), expectedId+index,
                                 "Wrong item in set when using limits.")
                index += 1

            self.assertEqual(index, limit,
                             "Number of iterations wrong with limits")

        # Check iteration with limit
        checkSetIteration(2)

        # Check iteration with limit and skip rows
        checkSetIteration(3, 2)

        # Tests unique method
        # Requesting 1 unique value as string
        result = imgSet.getUniqueValues("_samplingRate")
        self.assertEqual(len(result), 3, "Unique values wrong for 1 attribute and 3 value")

        # Requesting 1 unique value as list
        result = imgSet.getUniqueValues(["_samplingRate"])
        self.assertEqual(len(result), 3, "Unique values wrong for 1 attribute and one value as list")
        
        # Requesting several unique values as string
        result = imgSet.getUniqueValues("_index")
        self.assertEqual(len(result), 10, "Unique values wrong for id attribute")

        # Requesting several unique values with several columns
        result = imgSet.getUniqueValues(["_filename", "_samplingRate"])
        # Here we should have 2 keys containing 2 list
        self.assertEqual(len(result), 2, "Unique values dictionary length wrong")
        self.assertEqual(len(result["_filename"]), 3, "Unique values dict item size wrong")

        # Requesting unique values with where
        result = imgSet.getUniqueValues("_index",where="_samplingRate = 2")
        # Here we should have 2 values
        self.assertEqual(len(result), 3, "Unique values with filter not working")

        # Request id list
        result = imgSet.getUniqueValues(ID)
        # Here we should have 10 values
        self.assertEqual(len(result), 10, "Unique values with ID")

        # Use creation timestamp
        # Request id list
        result = imgSet.getUniqueValues(ID, where="%s>=%s" % (CREATION , imgSet.fmtDate(halfTimeStamp)))
        self.assertEqual(len(result), 5, "Unique values after a time stamp does not work")

        # Test getIdSet
        ids = imgSet.getIdSet()
        self.assertIsInstance(ids, set, "getIdSet does not return a set")
        self.assertIsInstance(next(iter(ids)), int, "getIdSet items are not integer")
        self.assertEqual(len(ids), 10, "getIdSet does not return 10 items")

        # Test load properties queries
        from pyworkflow.mapper.sqlite_db import logger
        logger.setLevel(DEBUG)
        lastResort.setLevel(DEBUG)
        imgSetVerbose = MockSetOfImages(filename=fn)
        imgSetVerbose.loadAllProperties()

        # Compare sets are "equal"
        self.compareSetProperties(imgSet, imgSetVerbose, ignore=[])


    def test_copyAttributes(self):
        """ Check that after copyAttributes, the values
        were properly copied.
        """
        c1 = Complex(imag=10., real=11.)
        c2 = Complex(imag=0., real=1.0001)
        
        # Float values are different, should not be equal
        self.assertFalse(c1.equalAttributes(c2))
        c2.copyAttributes(c1, 'imag', 'real')
        
        self.assertTrue(c1.equalAttributes(c2), 
                        'Complex c1 and c2 have not equal attributes'
                        '\nc1: %s\nc2: %s\n' % (c1, c2))

        c1.score = pwobj.Float(1.)

        # If we copyAttributes again, score dynamic attribute should
        # be set in c2
        c2.copyAttributes(c1, 'score')
        self.assertTrue(hasattr(c2, 'score'))
        
    def test_equalAttributes(self):
        """ Check that equal attributes function behaves well
        to compare floats with a given precision.
        """
        c1 = Complex(imag=0., real=1.)
        c2 = Complex(imag=0., real=1.0001)
        
        # Since Float precision is 0.001, now c1 and c2
        # should have equal attributes
        self.assertTrue(c1.equalAttributes(c2))
        # Now if we set a more restrictive precision
        # c1 and c2 are not longer equals
        pwobj.Float.setPrecision(0.0000001)
        self.assertFalse(c1.equalAttributes(c2))

    def test_formatString(self):
        """ Test that Scalar objects behave well
        when using string formatting such as: %f or %d
        """
        i = pwobj.Integer(10)
        f = pwobj.Float(3.345)
        
        s1 = "i = %d, f = %0.3f" % (i, f)
        
        self.assertEqual(s1, "i = 10, f = 3.345")

    def test_getObjDict(self):
        """ Test retrieving an object dictionary with its attribute values."""
        acq1 = MockAcquisition(magnification=50000,
                               voltage=200,
                               sphericalAberration=2.7,
                               dosePerFrame=1)
        m1 = MockMicrograph(
            'my_movie.mrc', objId=1, objLabel='test micrograph',
            objComment='Testing store and retrieve from dict.')
        m1.setSamplingRate(1.6)
        m1.setAcquisition(acq1)
        m1Dict = m1.getObjDict(includeBasic=True)

        goldDict1 = dict([
            ('object.id', 1),
            ('object.label', 'test micrograph'),
            ('object.comment', 'Testing store and retrieve from dict.'),
            ('_index', 0),
            ('_filename', 'my_movie.mrc'),
            ('_samplingRate', 1.6),
            ('_micName', None),
            ('_acquisition', None),
            ('_acquisition._magnification', 50000.0),
            ('_acquisition._voltage', 200.0),
            ('_acquisition._sphericalAberration', 2.7),
            ('_acquisition._amplitudeContrast', None),
            ('_acquisition._doseInitial', 0.0),
            ('_acquisition._dosePerFrame', 1.0),
             ])

        self.assertEqual(goldDict1, m1Dict)

    def test_Dict(self):
        d = pwobj.Dict(default='missing')
        d.update({1: 'one', 2: 'two'})

        # Return default value for any non-present key
        self.assertEqual('missing', d[10])

        # Return true for any 'contains' query
        self.assertTrue(100 in d)
        

class TestUtils(pwtests.BaseTest):

    @classmethod
    def setUpClass(cls):
        pwtests.setupTestOutput(cls)
            
    def test_ListsFunctions(self):
        """ Test of some methods that retrieve lists from string. """
        from pyworkflow.utils import getListFromValues, getFloatListFromValues,\
            getBoolListFromValues
        
        results = [('2x1 2x2 4 5', None, getListFromValues,
                    ['1', '1', '2', '2', '4', '5']),
                   ('2x1 2x2 4 5', None, getFloatListFromValues,
                    [1., 1., 2., 2., 4., 5.]),
                   ('1 2 3x3 0.5', 8, getFloatListFromValues,
                    [1., 2., 3., 3., 3., 0.5, 0.5, 0.5]),
                   ('3x1 3x0 1', 8, getBoolListFromValues,
                    [True, True, True, False, False, False, True, True]),
                   ]
        for s, n, func, goldList in results:
            l = func(s, length=n)
            self.assertAlmostEqual(l, goldList)
            if n:
                self.assertEqual(n, len(l))
                
    def test_Environ(self):
        """ Test the Environ class with its utilities. """
        from pyworkflow.utils import Environ
        env = Environ({'PATH': '/usr/bin:/usr/local/bin',
                       'LD_LIBRARY_PATH': '/usr/lib:/usr/lib64'
                       })
        env1 = Environ(env)
        env1.set('PATH', '/usr/local/xmipp')
        self.assertEqual(env1['PATH'], '/usr/local/xmipp')
        self.assertEqual(env1['LD_LIBRARY_PATH'], env['LD_LIBRARY_PATH'])
        
        env2 = Environ(env)
        env2.set('PATH', '/usr/local/xmipp', position=Environ.BEGIN)
        self.assertEqual(env2['PATH'], '/usr/local/xmipp' + os.pathsep +
                         env['PATH'])
        self.assertEqual(env2['LD_LIBRARY_PATH'], env['LD_LIBRARY_PATH'])
        
        env3 = Environ(env)
        env3.update({'PATH': '/usr/local/xmipp', 
                     'LD_LIBRARY_PATH': '/usr/local/xmipp/lib'},
                    position=Environ.END)
        self.assertEqual(env3['PATH'], env['PATH'] + os.pathsep +
                         '/usr/local/xmipp')
        self.assertEqual(env3['LD_LIBRARY_PATH'], env['LD_LIBRARY_PATH'] +
                         os.pathsep + '/usr/local/xmipp/lib')
