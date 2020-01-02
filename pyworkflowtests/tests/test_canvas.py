#!/usr/bin/env python
# To run only the tests in this file, use:
# python -m unittest test_canvas -v

import pyworkflow.gui.canvas
import tkinter
import math
from pyworkflow.tests import *


class TestCanvas(BaseTest):
    # IMPORTANT: Tk requires at least that DISPLAY is defined
    # hence in some environments (like buildbot) the test may fail,
    # check for the TclError exception
    
    _labels = [PULL_REQUEST] 
    
    @classmethod
    def setUpClass(cls):
        setupTestOutput(cls)

    def distance(self, c1, c2):
        return round(math.hypot(c2[0] - c1[0], c2[1] - c1[1]), 2)

    def allEqual(self, values):
        return not values or values.count(values[0]) == len(values)

    def allDifferent(self, values):
        return not values or len(values) == len(set(values))

    def test_connectorsCoords(self):
        try:
            root = tkinter.Tk()
            canvas = pyworkflow.gui.canvas.Canvas(root, width=800, height=600)
            tb1 = canvas.createTextbox("First", 100, 100, "blue")

            connectorsCoords = tb1.getConnectorsCoordinates()
            self.assertTrue(self.allDifferent(connectorsCoords))

            print(connectorsCoords)

            distances = {}
            for i in range(len(connectorsCoords)-1):
                distances[i] = self.distance(connectorsCoords[i],
                                             connectorsCoords[i+1])

                print(distances)
                self.assertTrue(self.allEqual(list(distances.values())))
                self.assertNotEqual(distances[0], 0)
        except tkinter.TclError as ex:
            print(ex)

    def test_closestConnectors(self):
        try:
            root = tkinter.Tk()
            canvas = pyworkflow.gui.canvas.Canvas(root, width=800, height=600)
            tb1 = canvas.createTextbox("Textbox1", 100, 100, "blue")
            tb2 = canvas.createTextbox("Textbox2", 300, 100, "blue")
            tb3 = canvas.createTextbox("Textbox3", 100, 300, "blue")

            tb1ConnectorsCoords = tb1.getConnectorsCoordinates()
            tb2ConnectorsCoords = tb2.getConnectorsCoordinates()
            tb3ConnectorsCoords = tb3.getConnectorsCoordinates()
            c1, c2= pyworkflow.gui.canvas.findStrictClosestConnectors(tb1, tb2)
            c3, c4= pyworkflow.gui.canvas.findStrictClosestConnectors(tb1, tb3)
            # tb1 and tb2 are aligned vertically. tb1 and tb3, horizontally.
            # So, their closest connectors must share one coordinate (y in case of c1&c2, x i n case of c3&c4)
            self.assertEqual(c1[1], c2[1])
            self.assertEqual(c3[0], c4[0])

        except tkinter.TclError as ex:
            print(ex)
