# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es)
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
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
"""
This module implement the classes to create plots on xmipp.
"""

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

from pyworkflow.viewer import View

figureCounter = 0


class Plotter(View):
    """ Create different types of plots using the matplotlib library. """
    backend = None
    
    @classmethod
    def setBackend(cls, value):
        """ Possible values are:
        - TkAgg for Tkinter
        - Agg for non-interactive plots.
        """
        plt.switch_backend(value)
        cls.backend = value
        
    def __init__(self, x=1, y=1, mainTitle="", 
                 figsize=None, dpi=100, windowTitle="",
                 fontsize=8, **kwargs):
        """ This Plotter class has some utilities to create a Matplotlib figure
        and add some plots to it.
        Params:
            x, y: number of rows and columns of the grid for plots.
            mainTitle: figure main title.
            figsize: the size of the figure, if None, it will be guessed from x and y
            dpi: resolution, 100 by default.
            windowTitle: title for the whole windows.
        """
        figure = kwargs.get('figure', None)

        if figure == 'active':
            figure = plt.gcf()
        
        if self.backend is None:
            Plotter.setBackend('Agg')

        plt.style.use(kwargs.get('style', 'default'))

        if figure is None:
            self.tightLayoutOn = True
            
            if figsize is None:  # Set some defaults values
                if x == 1 and y == 1:
                    figsize = (6, 5)
                elif x == 1 and y == 2:
                    figsize = (4, 6)
                elif x == 2 and y == 1:
                    figsize = (6, 4)
                else:
                    figsize = (8, 6)
            
            # Create grid
            # import matplotlib.gridspec as gridspec
            # self.grid = gridspec.GridSpec(x, y)#, height_ratios=[7,4])
            # self.grid.update(left=0.15, right=0.95, hspace=0.25, wspace=0.4)#, top=0.8, bottom=0.2)
            global figureCounter
            figureCounter += 1
            self.figure = plt.figure(figureCounter, figsize=figsize, dpi=dpi)
            # from matplotlib.figure import Figure
            # self.figure = Figure(figsize=figsize, dpi=dpi)
            if mainTitle:
                self.figure.suptitle(mainTitle, fontsize=fontsize + 4)
            if windowTitle:
                self.figure.canvas.manager.set_window_title(windowTitle)
            self.plot_count = 0
            self.last_subplot = None
            self.plot_yformat = '%1.2e'
        else:
            self.figure = figure
            self.tightLayoutOn = False
            self.plot_count = 0
            
        self.fontsize = fontsize
        self.plot_title_fontsize = fontsize + 4
        self.plot_axis_fontsize = fontsize + 2
        self.plot_text_fontsize = fontsize
        self.gridx = x
        self.gridy = y
            
    def activate(self):
        """ Activate this figure. """
        plt.figure(self.figure.number)
        
    def getCanvas(self):
        return self.figure.canvas
    
    def getFigure(self):
        return self.figure
    
    def showLegend(self, labels, loc='best'):
        leg = self.last_subplot.legend(tuple(labels), loc=loc)
        for t in leg.get_texts():
            t.set_fontsize(self.plot_axis_fontsize)    # the legend text fontsize

    def legend(self, loc='best', **kwargs):
        self.last_subplot.legend(loc=loc, **kwargs)

    def createSubPlot(self, title, xlabel, ylabel, xpos=None, ypos=None,
                      yformat=False, projection='rectilinear', subtitle=None
                      ):
        """
        Create a subplot in the figure.
        You should provide plot title, and x and y axis labels.
        yformat True specified the use of global self.plot_yformat
        Possible values for projection are:
            'aitoff', 'hammer', 'lambert', 'mollweide', 'polar', 'rectilinear'

        """
        if xpos is None:
            self.plot_count += 1
            pos = self.plot_count
        else:
            pos = xpos + (ypos - 1) * self.gridx
        a = self.figure.add_subplot(self.gridx, self.gridy, pos, projection=projection)
        # a.get_label().set_fontsize(12)
        a.set_title(title, fontsize=self.plot_title_fontsize)

        if subtitle:
            self.figure.text(0.5, 0.015, subtitle, horizontalalignment="center")

        def setTicksFont(labels):
            for label in labels:
                label.set_fontsize(self.plot_text_fontsize)  # Set fontsize

        if xlabel is not None:
            # Axis setup
            a.set_xlabel(xlabel, fontsize=self.plot_axis_fontsize)
            a.xaxis.get_label().set_fontsize(self.plot_axis_fontsize)
            setTicksFont(a.xaxis.get_ticklabels())

        if ylabel is not None:
            a.set_ylabel(ylabel, fontsize=self.plot_axis_fontsize)

            if yformat:
                import matplotlib.ticker as ticker
                formatter = ticker.FormatStrFormatter(self.plot_yformat)
                a.yaxis.set_major_formatter(formatter)
            a.yaxis.get_label().set_fontsize(self.plot_axis_fontsize)
            setTicksFont(a.yaxis.get_ticklabels())

        if xlabel is None and ylabel is None:
            a.axis('off')

        self.last_subplot = a
        self.plot = a.plot
        self.hist = a.hist
        self.scatterP = a.scatter
        self.bar = a.bar
        return a

    def getLastSubPlot(self):
        return self.last_subplot
    
    def createCanvas(self):
        a = self.figure.add_subplot(111, axisbg='g')
        a.set_axis_off()
        self.figure.set_facecolor('white')
        return a

    def getColorBar(self, plot):
        self.tightLayoutOn = False
        cax = self.figure.add_axes([0.9, 0.1, 0.03, 0.8])
        cbar = self.figure.colorbar(plot, cax=cax)
        cbar.set_ticks(cbar.get_ticks())
        cbar.ax.invert_yaxis()

    def tightLayout(self):
        if self.tightLayoutOn:
            self.activate()
            plt.tight_layout()
        
    def show(self, interactive=True, block=False):
        self.tightLayout()
        plt.show(block=block)

    def draw(self):
        self.tightLayout()
        self.getCanvas().draw()
        
    def clear(self):
        self.getFigure().clear()
        self.plot_count = 0
        self.last_subplot = None
        
    def savefig(self, *args, **kwargs):
        self.tightLayout()
        self.figure.savefig(*args, **kwargs)
        
    def isClosed(self):
        """ Return true if the figure have been closed. """
        return not plt.fignum_exists(self.figure.number)
    
    def close(self):
        """ Close current Plotter figure. """
        plt.close(self.figure)
        

def getHexColorList(numberOfColors, colorName='jet'):
    """ Returns a list of hexColor """
    from matplotlib import cm, colors
    
    colorsList = []
    colorMap = cm.get_cmap(colorName)
    ratio = colorMap.N / numberOfColors
    for index in range(numberOfColors):
        colorPosition = int(round((index * ratio)))
        rgb = colorMap(colorPosition)[:3]
        rgbColor = colors.rgb2hex(rgb)
        colorsList.append(rgbColor)

    return colorsList
