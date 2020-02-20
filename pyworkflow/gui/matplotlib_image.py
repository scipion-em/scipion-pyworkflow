# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es)
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 2 of the License, or
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
"""
Several Image tools using Matplotlib.
"""

import tkinter as tk
import matplotlib
import numpy as np

from pyworkflow import TK_GRAY_DEFAULT

try:
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

from matplotlib.figure import Figure
import matplotlib.cm as cm
from matplotlib.patches import Wedge


class FigureFrame(tk.Frame):
    """ Create a Tk Frame that will contains a 
    Matplotlib Figure. 
    **kwargs arguments will be passed to Figure constructor.
    Valid options are:
        figsize = (xdim, ydim)
        dpi = value
        frameon = (True|False)
    """
    def __init__(self, parent, **kwargs):
        tk.Frame.__init__(self, parent)
        self.figure = Figure(**kwargs)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().grid(column=0, row=0)

    def getFigure(self):
        return self.figure
    
    def getCanvas(self):
        return self.canvas
    
    
class Preview(tk.Frame):
    # def __init__(self, parent, dim, dpi=36, label=None):
    def __init__(self, parent, dim, dpi=36, label=None, col=0, row=0, listenersDict=None):
        tk.Frame.__init__(self, parent)
        self.dim = dim
        self.bg = np.zeros((int(dim), int(dim)), float)
        ddim = dim/dpi
        self.figure = Figure(figsize=(ddim, ddim), dpi=dpi, frameon=False)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().grid(column=0, row=0)  # , sticky=(N, W, E, S))
        self.canvas.get_tk_widget().config(bg=TK_GRAY_DEFAULT)
        if label:
            tk.Label(self, text=label).grid(column=0, row=1)
        self._createAxes()

        if listenersDict is not None:
            for bindingKey, callback in listenersDict.items():
                self.canvas.get_tk_widget().bind(bindingKey, callback)

    def setWindowTitle(self, title):
        """ Set window title"""
        self.canvas.set_window_title(title)

    def _createAxes(self):
        """ Should be implemented in subclasses. """
        pass
    
    def _update(self, *args):
        """ Should be implemented in subclasses. """
        pass
    
    def clear(self):
        self._update(self.bg)
        
    def updateData(self, Z):
        self.clear()
        self._update(Z)
    
    
class ImagePreview(Preview):
    def __init__(self, parent, dim, dpi=36, label=None, col=0, listenersDict=None):
        Preview.__init__(self, parent, dim, dpi, label, col, listenersDict=listenersDict)
            
    def _createAxes(self):
        ax = self.figure.add_axes([0, 0, 1, 1], frameon=False)
        self.figureimg = ax.imshow(self.bg, cmap=cm.gray)  # , extent=[-h, h, -h, h])
        ax.set_axis_off()
        self.ax = ax
        
    def _update(self, Z, *args):
        self.figureimg.set_data(Z)
        self.figureimg.autoscale()
        self.figureimg.set(extent=[0, Z.shape[1], 0, Z.shape[0]])
        self.canvas.draw()
        
        
class PsdPreview(Preview):
    def __init__(self, master, dim, lf, hf, dpi=72, label="PSD", listenersDict=None):
        Preview.__init__(self, master, dim, dpi, label, listenersDict=listenersDict)
        self.lf = lf
        self.hf = hf
        if self.ring:
            self.createRing()
        else:
            self.canvas.draw()
                            
    def _createAxes(self):
        ax = self.figure.add_axes([0, 0, 1, 1], frameon=False)
        h = 0.5
        ax.set_xlim(-h, h)
        ax.set_ylim(-h, h)
        ax.tick_params(axis="x", direction="in", pad=-15)
        ax.tick_params(axis="y", direction="in", pad=-22)
        ax.grid(True)
        self.ring = None
        self.img = ax.imshow(self.bg, cmap=cm.gray, extent=[-h, h, -h, h])
        self.ax = ax
        
    def createRing(self, fc=None):
        radius = float(self.hf)
        width = radius - float(self.lf)
        self.ring = Wedge((0, 0), radius, 0, 360, width=width, alpha=0.15, fc=fc)  # Full ring
        self.ax.add_patch(self.ring)
        self.canvas.draw()
        
    def updateFreq(self, lf, hf):
        self.lf = lf
        self.hf = hf
        if self.ring:
            self.ring.remove()
            self.ring = None
        if self.hf:
            self.createRing()
    
    def _update(self, Z):
        if self.ring:
            self.ring.remove()
            self.ring = None
        if self.hf:
            self.createRing()
        self.img.set_data(Z)
        self.img.autoscale()
        self.canvas.draw()
        
        
class MaskPreview(ImagePreview):
    def __init__(self, parent, dim, dpi=36, label=None, col=0, listenersDict=None):
        ImagePreview.__init__(self, parent, dim, dpi, label, col, listenersDict)
        self.ring = None
            
    def updateMask(self, outerRadius, innerRadius=0, fc=None):
        if self.ring is not None:
            self.ring.remove()
        center = self.dim / 2
        width = outerRadius - innerRadius
        self.ring = Wedge((center, center), outerRadius, 0, 360, width=width, alpha=0.15, fc=fc)  # Full ring
        self.ax.add_patch(self.ring)
        self.canvas.draw()
        

def getPngData(filename):
    import matplotlib.image as mpimg
    return mpimg.imread(filename)


def createBgImage(dim):
    return np.ones((dim, dim, 3))
