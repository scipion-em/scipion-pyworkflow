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


import pyworkflow as pw
import pyworkflow.object as pwobj
import pyworkflow.tests as pwtests
import pyworkflow.mapper as pwmapper
from pyworkflow.mapper.sqlite import ID
from pyworkflowtests.objects import Complex, MockImage
import pyworkflowtests

IMAGES_STK = 'images.stk'


class TestSqliteMapper(pwtests.BaseTest):
    @classmethod
    def setUpClass(cls):
        pwtests.setupTestOutput(cls)

    def test_SqliteMapper(self):
        fn = self.getOutputPath("basic.sqlite")
        mapper = pwmapper.SqliteMapper(fn)

        # Insert a Float
        f = pwobj.Float(5.4)
        mapper.insert(f)

        # Insert an pwobj.Integer
        i = pwobj.Integer(1)
        mapper.insert(i)

        # Insert two pwobj.Boolean
        b = pwobj.Boolean(False)
        b2 = pwobj.Boolean(True)
        mapper.insert(b)
        mapper.insert(b2)

        # Test storing pointers
        p = pwobj.Pointer(b)
        mapper.insert(p)

        # Store csv list
        strList = ['1', '2', '3']
        csv = pwobj.CsvList()
        csv += strList
        mapper.insert(csv)

        # Test normal List
        iList = pwobj.List()
        mapper.insert(iList)  # Insert the list when empty
        i1 = pwobj.Integer(4)
        i2 = pwobj.Integer(3)
        iList.append(i1)
        iList.append(i2)
        mapper.update(iList)  # now update with some items inside

        pList = pwobj.PointerList()
        p1 = pwobj.Pointer(b)
        # p1.set(b)
        p2 = pwobj.Pointer(b2)
        # p2.set(b2)
        pList.append(p1)
        pList.append(p2)
        mapper.store(pList)

        # Test to add relations
        relName = 'testRelation'
        creator = f
        mapper.insertRelation(relName, creator, i, b)
        mapper.insertRelation(relName, creator, i, b2)

        mapper.insertRelation(relName, creator, b, p)
        mapper.insertRelation(relName, creator, b2, p)

        # Save changes to file
        mapper.commit()
        self.assertEqual(1, mapper.db.getVersion())
        mapper.close()

        # Test using SqliteDb class
        db = pwmapper.SqliteDb()
        db._createConnection(fn, timeout=1000)
        tables = ['Objects', 'Relations']
        self.assertEqual(tables, db.getTables())
        # Test getting the version, for the gold file it should be 0
        self.assertEqual(1, db.getVersion())
        db.close()

        # Reading test
        mapper2 = pwmapper.SqliteMapper(fn, pw.Config.getDomain().getMapperDict())
        print("Checking that Relations table is updated and version to 1")
        self.assertEqual(1, mapper2.db.getVersion())
        # Check that the new column is properly added after updated to version 1
        colNamesGold = [u'id', u'parent_id', u'name', u'classname',
                        u'value', u'label', u'comment', u'object_parent_id',
                        u'object_child_id', u'creation',
                        u'object_parent_extended', u'object_child_extended']
        colNames = [col[1] for col in mapper2.db.getTableColumns('Relations')]
        self.assertEqual(colNamesGold, colNames)

        l = mapper2.selectByClass('Integer')[0]
        self.assertEqual(l.get(), 1)

        f2 = mapper2.selectByClass('Float')[0]
        self.assertEqual(f, f2.get())

        b = mapper2.selectByClass('Boolean')[0]
        self.assertTrue(not b.get())

        p = mapper2.selectByClass('Pointer')[0]
        self.assertEqual(b.get(), p.get())

        csv2 = mapper2.selectByClass('CsvList')[0]
        self.assertTrue(list.__eq__(csv2, strList))

        # Iterate over all objects
        allObj = mapper2.selectAll()
        iterAllObj = mapper2.selectAll(iterate=True)

        for a1, a2 in zip(allObj, iterAllObj):
            # Note compare the scalar objects, which have a well-defined comparison
            if isinstance(a1, pwobj.Scalar):
                self.assertEqual(a1, a2)

        # Test select all batch approach
        allBatch = mapper2.selectAllBatch()

        # Test relations
        childs = mapper2.getRelationChilds(relName, i)
        parents = mapper2.getRelationParents(relName, p)
        # In this case both childs and parent should be the same
        for c, p in zip(childs, parents):
            self.assertEqual(c, p,
                             "Childs of object i, should be the parents of object p")

        relations = mapper2.getRelationsByCreator(creator)
        for row in relations:
            print(dict(row))

    def test_StorePointers(self):
        """ Check that pointers are correctly stored. """
        fn = self.getOutputPath("pointers.sqlite")

        print(">>> Using db: ", fn)

        mapper = pwmapper.SqliteMapper(fn)
        # Insert a Complex
        c = Complex.createComplex()  # real = 1, imag = 1
        mapper.insert(c)
        # Insert an pwobj.Integer
        p1 = pwobj.Pointer(c)
        p1.setExtended('real')

        mapper.store(c)
        mapper.store(p1)

        self.assertAlmostEqual(c.real.get(), p1.get().get())

        p1.set(None)  # Reset value and check that is stored properly

        self.assertIsNone(p1._extended.get())
        mapper.store(p1)
        mapper.commit()

        mapper2 = pwmapper.SqliteMapper(fn, pw.Config.getDomain().getMapperDict())
        p2 = mapper2.selectByClass('Pointer')[0]

        # Check the mapper was properly stored when
        # set to None and the _extended property cleaned
        self.assertIsNone(p2.get())

    def test_removeFromLists(self):
        """ Check that lists are properly stored after removing some elements.
        """
        fn = self.getOutputPath("lists.sqlite")

        print(">>> Using db: ", fn)

        # Let's create a Mapper to store a simple List containing two integers
        mapper = pwmapper.SqliteMapper(fn, pw.Config.getDomain().getMapperDict())
        iList = pwobj.List()
        i1 = pwobj.Integer(4)
        i2 = pwobj.Integer(3)
        iList.append(i1)
        iList.append(i2)
        # Store the list and commit changes to db, then close db.
        mapper.store(iList)
        mapper.commit()
        mapper.close()

        # Now let's open again the db with a different connection
        # and load the previously stored list
        mapper2 = pwmapper.SqliteMapper(fn, pw.Config.getDomain().getMapperDict())
        iList2 = mapper2.selectByClass('List')[0]
        # Let's do some basic checks
        self.assertEqual(iList2.getSize(), 2)
        self.assertTrue(pwobj.Integer(4) in iList2)
        self.assertTrue(pwobj.Integer(3) in iList2)

        # Now remove one of the integers in the list
        # check consistency in the list elements
        iList2.remove(pwobj.Integer(4))
        self.assertEqual(iList2.getSize(), 1)
        self.assertTrue(pwobj.Integer(4) not in iList2)
        self.assertTrue(pwobj.Integer(3) in iList2)
        # Store once again the new list with one element
        mapper2.store(iList2)
        mapper2.commit()
        mapper2.close()

        # Open the db and load the list once again
        mapper3 = pwmapper.SqliteMapper(fn, pw.Config.getDomain().getMapperDict())
        iList3 = mapper3.selectByClass('List')[0]
        # Check the same consistency before it was stored
        self.assertEqual(iList3.getSize(), 1)
        self.assertTrue(pwobj.Integer(4) not in iList3)
        self.assertTrue(pwobj.Integer(3) in iList3)


class TestSqliteFlatMapper(pwtests.BaseTest):
    """ Some tests for DataSet implementation. """
    _labels = [pwtests.SMALL]

    @classmethod
    def setUpClass(cls):
        pwtests.setupTestOutput(cls)

        # This isSet the application domain
        pyworkflowtests.Domain = pyworkflowtests.TestDomain
        pw.Config.setDomain("pyworkflowtests")

    # TODO: Maybe some mapper test for backward compatibility can be
    def test_insertObjects(self):
        dbName = self.getOutputPath('images.sqlite')
        print(">>> test_insertObjects: dbName = '%s'" % dbName)
        mapper = pwmapper.SqliteFlatMapper(dbName, pw.Config.getDomain().getMapperDict())
        self.assertEqual(0, mapper.count())
        self.assertEqual(0, mapper.maxId())
        n = 10

        indexes = list(range(1, n + 1))
        for i in indexes:
            img = MockImage()
            img.setLocation(i, IMAGES_STK)
            img.setSamplingRate(i%2)
            mapper.insert(img)

        self.assertEqual(n, mapper.count())
        self.assertEqual(n, mapper.maxId())

        # Store one more image with bigger id
        img = MockImage()
        bigId = 1000
        img.setLocation(i + 1, IMAGES_STK)
        img.setObjId(bigId)
        mapper.insert(img)
        self.assertEqual(bigId, mapper.maxId())

        # Insert another image with None as id, it should take bigId + 1
        img.setLocation(i + 2, IMAGES_STK)
        img.setObjId(None)
        mapper.insert(img)
        self.assertEqual(bigId + 1, mapper.maxId())

        mapper.setProperty('samplingRate', '3.0')
        mapper.setProperty('defocusU', 1000)
        mapper.setProperty('defocusV', 1000)
        mapper.setProperty('defocusU', 2000)  # Test update a property value
        mapper.deleteProperty('defocusV')  # Test delete a property
        mapper.commit()
        self.assertEqual(1, mapper.db.getVersion())

        # Test where parsing
        self.assertIsNone(mapper.db._whereToWhereStr(None), "A where = None does not return None")
        self.assertEqual(mapper.db._whereToWhereStr("missing1=missing2"), "missing1=missing2", "a where with missing fields does not work")
        self.assertEqual(mapper.db._whereToWhereStr("_samplingRate=value2"), "c03=value2", "simple = where does not work")
        self.assertEqual(mapper.db._whereToWhereStr("_samplingRate=_samplingRate"), "c03=c03", "simple = where with 2 fields does not work")
        self.assertEqual(mapper.db._whereToWhereStr("_samplingRate = _samplingRate"), "c03 = c03", "simple = spaced where with 2 fields does not work")
        self.assertEqual(mapper.db._whereToWhereStr("_samplingRate < 3"), "c03 < 3", "a where with < does not work")
        self.assertEqual(mapper.db._whereToWhereStr("_samplingRate >= 4"), "c03 >= 4", "a where with >= does not work")
        self.assertEqual(mapper.db._whereToWhereStr("5 <= _samplingRate"), "5 <= c03", "a where with <= does not work")
        self.assertEqual(mapper.db._whereToWhereStr("5 <= _samplingRate OR 3=_index"), "5 <= c03 OR 3=c01", "a where with OR does not work")

        # Tests actual where used in queries
        self.assertEqual(len(mapper.unique(ID, "_index = 1 OR _index = 2")), 2, "unique with OR in where does not work.")
        self.assertEqual(len(mapper.unique(ID, ID + " >= 20 ")), 2, "unique >= in where does not work.")
        mapper.close()

        # Test that values were stored properly
        mapper2 = pwmapper.SqliteFlatMapper(dbName, pw.Config.getDomain().getMapperDict())
        indexes.extend([bigId, bigId + 1])
        for i, obj in enumerate(mapper2.selectAll(iterate=True)):
            self.assertEqual(obj.getIndex(), i + 1)
            self.assertEqual(obj.getObjId(), indexes[i])

        self.assertTrue(mapper2.hasProperty('samplingRate'))
        self.assertTrue(mapper2.hasProperty('defocusU'))
        self.assertFalse(mapper2.hasProperty('defocusV'))

        self.assertEqual(mapper2.getProperty('samplingRate'), '3.0')
        self.assertEqual(mapper2.getProperty('defocusU'), '2000')

        # Make sure that maxId() returns the proper value after loading db
        self.assertEqual(bigId + 1, mapper2.maxId())

        # test aggregation
        result = mapper2.aggregate("COUNT", "id")  # As strings
        self.assertEqual(result[0]["COUNT"], 12, "Aggregation fo count does not work")

        result = mapper2.aggregate(["COUNT"], ["id"])  # As lists
        self.assertEqual(result[0]["COUNT"], 12, "Aggregation as list of count does not work")

        result = mapper2.aggregate(["MAX","AVG"], "id")
        self.assertEqual(result[0]["MAX"], bigId+1, "Aggregation  max, avg does not work")
        self.assertAlmostEqual(result[0]["AVG"], 171.33, places=2, msg="Aggregation  max, avg does not work")

        result = mapper2.aggregate(["MAX", "COUNT"], "_samplingRate", "id")
        self.assertEqual(result[0]["MAX"], 1, "Aggregation max, grouped does not work")
        self.assertEqual(result[0]["COUNT"], 1, "Aggregation  max, count does not work")
        self.assertEqual(result[0]["id"], 1, "Aggregation  group field not returned")

        # Aggregation on more than one field
        result = mapper2.aggregate(["MAX"], ["id","_samplingRate"])
        self.assertEqual(result[0]["MAX"], 1001, "Aggregation max, grouped does not work")
        self.assertEqual(result[0]["MAX_samplingRate"], 1.0, "Aggregation  max, count does not work")

    def test_emtpySet(self):
        dbName = self.getOutputPath('empty.sqlite')
        print(">>> test empty set: dbName = '%s'" % dbName)
        # Check that writing an emtpy set do not fail
        objSet = pwobj.Set(filename=dbName)
        objSet.write()
        objSet.close()
        # Now let's try to open an empty set
        objSet = pwobj.Set(filename=dbName)
        self.assertEqual(objSet.getSize(), 0)
        items = [obj.clone() for obj in objSet]
        self.assertEqual(len(items), 0)


class TestDataSet(pwtests.BaseTest):
    """ Some tests for DataSet implementation. """

    @classmethod
    def setUpClass(cls):
        pwtests.setupTestOutput(cls)

    def test_Table(self):
        from pyworkflow.utils.dataset import Table, Column
        table = Table(Column('x', int, 5),
                      Column('y', float, 0.0),
                      Column('name', str))

        # Add a row to the table
        table.addRow(1, x=12, y=11.0, name='jose')
        table.addRow(2, x=22, y=21.0, name='juan')
        table.addRow(3, x=32, y=31.0, name='pedro')
        # Expect an exception, since name is not provided and have not default
        self.assertRaises(Exception, table.addRow, 100, y=3.0)
        row = table.getRow(1)
        print(row)
        self.assertEqual(table.getSize(), 3, "Bad table size")

        # Update a value of a row
        table.updateRow(1, name='pepe')
        row = table.getRow(1)
        print(row)
        self.assertEqual(row.name, 'pepe', "Error updating name in row")
