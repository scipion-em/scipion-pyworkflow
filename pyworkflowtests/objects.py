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
"""
Definition of Mock objects to be used within the tests in the Mock Domain
"""

import os

import pyworkflow.object as pwobj

NO_INDEX = 0


class MockObject(pwobj.OrderedObject):
    """Base object for all Mock classes"""
    def __init__(self, **kwargs):
        pwobj.OrderedObject.__init__(self, **kwargs)

    def __str__(self):
        return self.getClassName()

    def getFiles(self):
        """ Get all filePaths """
        return None


class Complex(MockObject):
    """ Simple class used for tests here. """

    cGold = complex(1.0, 1.0)

    def __init__(self, imag=0., real=0., **args):
        MockObject.__init__(self, **args)
        self.imag = pwobj.Float(imag)
        self.real = pwobj.Float(real)
        # Create reference complex values

    def __str__(self):
        return '(%s, %s)' % (self.imag, self.real)

    def __eq__(self, other):
        return (self.imag == other.imag and
                self.real == other.real)

    def hasValue(self):
        return True

    @classmethod
    def createComplex(cls):
        """Create a Complex object and set
        values with cls.cGold standard"""
        c = Complex()  # Create Complex object and set values
        c.imag.set(cls.cGold.imag)
        c.real.set(cls.cGold.real)
        return c


class MockAcquisition(MockObject):
    """Acquisition information"""
    def __init__(self, **kwargs):
        MockObject.__init__(self, **kwargs)
        self._magnification = pwobj.Float(kwargs.get('magnification', None))
        # Microscope voltage in kV
        self._voltage = pwobj.Float(kwargs.get('voltage', None))
        # Spherical aberration in mm
        self._sphericalAberration = pwobj.Float(kwargs.get('sphericalAberration',
                                                           None))
        self._amplitudeContrast = pwobj.Float(kwargs.get('amplitudeContrast', None))
        self._doseInitial = pwobj.Float(kwargs.get('doseInitial', 0))
        self._dosePerFrame = pwobj.Float(kwargs.get('dosePerFrame', None))

    def copyInfo(self, other):
        self.copyAttributes(other, '_magnification', '_voltage',
                            '_sphericalAberration', '_amplitudeContrast',
                            '_doseInitial', '_dosePerFrame')

    def getMagnification(self):
        return self._magnification.get()

    def setMagnification(self, value):
        self._magnification.set(value)

    def getVoltage(self):
        return self._voltage.get()

    def setVoltage(self, value):
        self._voltage.set(value)

    def getSphericalAberration(self):
        return self._sphericalAberration.get()

    def setSphericalAberration(self, value):
        self._sphericalAberration.set(value)

    def getAmplitudeContrast(self):
        return self._amplitudeContrast.get()

    def setAmplitudeContrast(self, value):
        self._amplitudeContrast.set(value)

    def getDoseInitial(self):
        return self._doseInitial.get()

    def setDoseInitial(self, value):
        self._doseInitial.set(value)

    def getDosePerFrame(self):
        return self._dosePerFrame.get()

    def setDosePerFrame(self, value):
        self._dosePerFrame.set(value)

    def __str__(self):
        return "\n    mag=%s\n    volt= %s\n    Cs=%s\n    Q0=%s\n\n" % \
               (self._magnification.get(),
                self._voltage.get(),
                self._sphericalAberration.get(),
                self._amplitudeContrast.get())


class MockImageDim(pwobj.CsvList):
    """ Just a wrapper to a pwobj.CsvList to store image dimensions
    as X, Y and Z.
    """
    def __init__(self, x=None, y=None, z=None):
        pwobj.CsvList.__init__(self, pType=int)
        if x is not None and y is not None:
            self.append(x)
            self.append(y)
            if z is not None:
                self.append(z)

    def getX(self):
        return self[0]

    def getY(self):
        return self[1]

    def getZ(self):
        return self[2]

    def __str__(self):
        if self.isEmpty():
            s = 'No-Dim'
        else:
            s = '%d x %d' % (self.getX(), self.getY())
            if self.getZ() > 1:
                s += ' x %d' % self.getZ()
        return s


class MockImage(MockObject):
    """Represents an EM Image object"""
    def __init__(self, location=None, **kwargs):
        """
         Params:
        :param location: Could be a valid location: (index, filename)
        or  filename
        """
        MockObject.__init__(self, **kwargs)
        # Image location is composed by an index and a filename
        self._index = pwobj.Integer(0)
        self._filename = pwobj.String()
        self._samplingRate = pwobj.Float()
        self._ctfModel = None
        self._acquisition = None
        if location:
            self.setLocation(location)

    def getSamplingRate(self):
        """ Return image sampling rate. (A/pix) """
        return self._samplingRate.get()

    def setSamplingRate(self, sampling):
        self._samplingRate.set(sampling)

    def getFormat(self):
        pass

    def getDataType(self):
        pass

    def getDimensions(self):
        """getDimensions is redundant here but not in setOfVolumes
         create it makes easier to create protocols for both images
         and sets of images
        """
        return self.getDim()

    def getDim(self):
        return 0, 0, 0  # We don't need dim now

    def getXDim(self):
        return self.getDim()[0] if self.getDim() is not None else 0

    def getYDim(self):
        return self.getDim()[1] if self.getDim() is not None else 0

    def getIndex(self):
        return self._index.get()

    def setIndex(self, index):
        self._index.set(index)

    def getFileName(self):
        """ Use the _objValue attribute to store filename. """
        return self._filename.get()

    def setFileName(self, filename):
        """ Use the _objValue attribute to store filename. """
        self._filename.set(filename)

    def getLocation(self):
        """ This function return the image index and filename.
        It will only differs from getFileName, when the image
        is contained in a stack and the index make sense.
        """
        return self.getIndex(), self.getFileName()

    def setLocation(self, *args):
        """ Set the image location, see getLocation.
        Params:
            First argument can be:
             1. a tuple with (index, filename)
             2. a index, this implies a second argument with filename
             3. a filename, this implies index=NO_INDEX
        """
        first = args[0]
        t = type(first)
        if t == tuple:
            index, filename = first
        elif t == int:
            index, filename = first, args[1]
        elif t == str:
            index, filename = NO_INDEX, first
        else:
            raise Exception('setLocation: unsupported type %s as input.' % t)

        self.setIndex(index)
        self.setFileName(filename)

    def getBaseName(self):
        return os.path.basename(self.getFileName())

    def copyInfo(self, other):
        """ Copy basic information """
        self.copyAttributes(other, '_samplingRate')

    def copyLocation(self, other):
        """ Copy location index and filename from other image. """
        self.setIndex(other.getIndex())
        self.setFileName(other.getFileName())

    def hasCTF(self):
        return self._ctfModel is not None

    def getCTF(self):
        """ Return the CTF model """
        return self._ctfModel

    def setCTF(self, newCTF):
        self._ctfModel = newCTF

    def hasAcquisition(self):
        return (self._acquisition is not None and
                self._acquisition.getVoltage() is not None and
                self._acquisition.getMagnification() is not None
                )

    def getAcquisition(self):
        return self._acquisition

    def setAcquisition(self, acquisition):
        self._acquisition = acquisition

    def hasTransform(self):
        return self._transform is not None

    def getTransform(self):
        return self._transform

    def setTransform(self, newTransform):
        self._transform = newTransform

    def hasOrigin(self):
        return self._origin is not None

    def getOrigin(self, force=False):
        """shifts in A"""
        if self.hasOrigin():
            return self._origin
        else:
            if force:
                return self._getDefaultOrigin()
            else:
                return None

    def _getDefaultOrigin(self):
        # original code from em required Transform, which will require
        # Matrix and then import numpy. Since this method is not used in
        # the tests I'm emptying it.
        pass

    def getShiftsiftsFromOrigin(self):
        origin = self.getOrigin(force=True).getShifts()
        x = origin[0]
        y = origin[1]
        z = origin[2]
        return x, y, z
        # x, y, z are floats in Angstroms

    def setShiftsInOrigin(self, x, y, z):
        origin = self.getOrigin(force=True)
        origin.setShifts(x, y, z)

    def setOrigin(self, newOrigin):
        """shifts in A"""
        self._origin = newOrigin

    def originResampled(self, originNotResampled, oldSampling):
        factor = self.getSamplingRate() / oldSampling
        shifts = originNotResampled.getShifts()
        origin = self.getOrigin(force=True)
        origin.setShifts(shifts[0] * factor,
                         shifts[1] * factor,
                         shifts[2] * factor)
        return origin

    def __str__(self):
        """ String representation of an Image. """
        dim = self.getDim()
        dimStr = str(MockImageDim(*dim)) if dim else 'No-Dim'
        return ("%s (%s, %0.2f Å/px)"
                % (self.getClassName(), dimStr,
                   self.getSamplingRate() or 99999.))

    def getFiles(self):
        filePaths = set()
        filePaths.add(self.getFileName())
        return filePaths


class MockMicrograph(MockImage):
    """ Represents an EM Micrograph object """
    def __init__(self, location=None, **kwargs):
        MockImage.__init__(self, location, **kwargs)
        self._micName = pwobj.String()

    def setMicName(self, micName):
        self._micName.set(micName)

    def getMicName(self):
        if self._micName.get():
            return self._micName.get()
        else:
            self.getFileName()

    def copyInfo(self, other):
        """ Copy basic information """
        MockImage.copyInfo(self, other)
        self.setMicName(other.getMicName())


class MockParticle(MockImage):
    """ Represents an EM Particle object """
    def __init__(self, location=None, **kwargs):
        MockImage.__init__(self, location, **kwargs)
        # This may be redundant, but make the Particle
        # object more indenpent for tracking coordinates
        self._coordinate = None
        self._micId = pwobj.Integer()
        self._classId = pwobj.Integer()

    def hasCoordinate(self):
        return self._coordinate is not None

    def setCoordinate(self, coordinate):
        self._coordinate = coordinate

    def getCoordinate(self):
        return self._coordinate

    def scaleCoordinate(self, factor):
        self.getCoordinate().scale(factor)

    def getMicId(self):
        """ Return the micrograph id if the coordinate is not None.
        or have set the _micId property.
        """
        if self._micId.hasValue():
            return self._micId.get()
        if self.hasCoordinate():
            return self.getCoordinate().getMicId()

        return None

    def setMicId(self, micId):
        self._micId.set(micId)

    def hasMicId(self):
        return self.getMicId() is not None

    def getClassId(self):
        return self._classId.get()

    def setClassId(self, classId):
        self._classId.set(classId)

    def hasClassId(self):
        return self._classId.hasValue()


class MockSet(pwobj.Set, MockObject):

    def _loadClassesDict(self):
        from pyworkflow.plugin import Domain
        classDict = Domain.getObjects()
        classDict.update(globals())

        return classDict

    def copyInfo(self, other):
        """ Define a dummy copyInfo function to be used
        for some generic operations on sets.
        """
        pass

    def clone(self):
        """ Override the clone defined in Object
        to avoid copying _mapperPath property
        """
        pass

    def copyItems(self, otherSet,
                  updateItemCallback=None,
                  itemDataIterator=None,
                  copyDisabled=False):
        """ Copy items from another set.
        If the updateItemCallback is passed, it will be
        called with each item (and optionally with a data row).
        This is a place where items can be updated while copying.
        This is useful to set new attributes or update values
        for each item.
        """
        for item in otherSet:
            # copy items if enabled or copyDisabled=True
            if copyDisabled or item.isEnabled():
                newItem = item.clone()
                if updateItemCallback:
                    row = None if itemDataIterator is None \
                        else next(itemDataIterator)
                    updateItemCallback(newItem, row)
                # If updateCallBack function returns attribute
                # _appendItem to False do not append the item
                if getattr(newItem, "_appendItem", True):
                    self.append(newItem)
            else:
                if itemDataIterator is not None:
                    next(itemDataIterator)  # just skip disabled data row

    def getFiles(self):
        return pwobj.Set.getFiles(self)


class MockSetOfImages(MockSet):
    """ Represents a set of Images """
    ITEM_TYPE = MockImage

    def __init__(self, **kwargs):
        MockSet.__init__(self, **kwargs)
        self._samplingRate = pwobj.Float()
        self._hasCtf = pwobj.Boolean(kwargs.get('ctf', False))
        self._isPhaseFlipped = pwobj.Boolean(False)
        self._isAmplitudeCorrected = pwobj.Boolean(False)
        self._acquisition = MockAcquisition()
        self._firstDim = MockImageDim()  # Dimensions of the first image

    def getAcquisition(self):
        return self._acquisition

    def setAcquisition(self, acquisition):
        self._acquisition = acquisition

    def hasAcquisition(self):
        return self._acquisition.getMagnification() is not None

    def append(self, image):
        """ Add a image to the set. """
        # If the sampling rate was set before, the same value
        # will be set for each image added to the set
        if self.getSamplingRate() or not image.getSamplingRate():
            image.setSamplingRate(self.getSamplingRate())
        # Copy the acquistion from the set to images
        # only override image acquisition if setofImages acquisition
        # is not none
        if self.hasAcquisition():
            # TODO: image acquisition should not be overwritten
            if not image.hasAcquisition():
                image.setAcquisition(self.getAcquisition())
        # Store the dimensions of the first image, just to
        # avoid reading image files for further queries to dimensions
        # only check this for first time append is called
        if self.isEmpty():
            self._setFirstDim(image)

        MockSet.append(self, image)

    def _setFirstDim(self, image):
        """ Store dimensions when the first image is found.
        This function should be called only once, to avoid reading
        dimension from image file. """
        if self._firstDim.isEmpty():
            self._firstDim.set(image.getDim())

    def copyInfo(self, other):
        """ Copy basic information (sampling rate and ctf)
        from other set of images to current one"""
        self.copyAttributes(other, '_samplingRate', '_isPhaseFlipped',
                            '_isAmplitudeCorrected', '_alignment')
        self._acquisition.copyInfo(other._acquisition)

    def getFiles(self):
        filePaths = set()
        uniqueFiles = self.aggregate(['count'], '_filename', ['_filename'])

        for row in uniqueFiles:
            filePaths.add(row['_filename'])
        return filePaths

    def setDownsample(self, downFactor):
        """ Update the values of samplingRate and scannedPixelSize
        after applying a downsampling factor of downFactor.
        """
        self.setSamplingRate(self.getSamplingRate() * downFactor)

    def setSamplingRate(self, samplingRate):
        """ Set the sampling rate and adjust the scannedPixelSize. """
        self._samplingRate.set(samplingRate)

    def getSamplingRate(self):
        return self._samplingRate.get()

    def getDim(self):
        """ Return the dimensions of the first image in the set. """
        if self._firstDim.isEmpty():
            return None
        x, y, z = self._firstDim
        return x, y, z

    def setDim(self, newDim):
        self._firstDim.set(newDim)

    def getXDim(self):
        return self.getDim()[0] if self.getDim() is not None else 0

    def isOddX(self):
        """ Return True if the first item x dimension is odd. """
        return self.getXDim() % 2 == 1

    def getDimensions(self):
        """Return first image dimensions as a tuple: (xdim, ydim, zdim)"""
        return self.getFirstItem().getDim()

    def __str__(self):
        """ String representation of a set of images. """
        sampling = self.getSamplingRate()

        if not sampling:
            print("FATAL ERROR: Object %s has no sampling rate!!!"
                  % self.getName())
            sampling = -999.0

        s = "%s (%d items, %s, %0.2f Å/px%s)" % \
            (self.getClassName(), self.getSize(),
             self._dimStr(), sampling, self._appendStreamState())
        return s

    def _dimStr(self):
        """ Return the string representing the dimensions. """
        return str(self._firstDim)

    def iterItems(self, orderBy='id', direction='ASC', where='1', limit=None):
        """ Redefine iteration to set the acquisition to images. """
        for img in pwobj.Set.iterItems(self, orderBy=orderBy, direction=direction,
                                       where=where, limit=limit):

            # Sometimes the images items in the set could
            # have the acquisition info per data row and we
            # don't want to override with the set acquisition for this case
            if not img.hasAcquisition():
                img.setAcquisition(self.getAcquisition())
            yield img

    def appendFromImages(self, imagesSet):
        """ Iterate over the images and append
        every image that is enabled.
        """
        for img in imagesSet:
            if img.isEnabled():
                self.append(img)

    def appendFromClasses(self, classesSet):
        """ Iterate over the classes and the element inside each
        class and append to the set all that are enabled.
        """
        for cls in classesSet:
            if cls.isEnabled() and cls.getSize() > 0:
                for img in cls:
                    if img.isEnabled():
                        self.append(img)


class MockSetOfMicrographs(MockSetOfImages):
    """ Create a base class for both Micrographs and Movies,
    but avoid to select Movies when Micrographs are required.
    """
    ITEM_TYPE = MockMicrograph

    def __init__(self, **kwargs):
        MockSetOfImages.__init__(self, **kwargs)
        self._scannedPixelSize = pwobj.Float()

    def copyInfo(self, other):
        """ Copy basic information (voltage, spherical aberration and
        sampling rate) from other set of micrographs to current one.
        """
        MockSetOfImages.copyInfo(self, other)
        self._scannedPixelSize.set(other.getScannedPixelSize())

    def setSamplingRate(self, samplingRate):
        """ Set the sampling rate and adjust the scannedPixelSize. """
        self._samplingRate.set(samplingRate)
        mag = self._acquisition.getMagnification()
        if mag is None:
            self._scannedPixelSize.set(None)
        else:
            self._scannedPixelSize.set(1e-4 * samplingRate * mag)

    def getScannedPixelSize(self):
        return self._scannedPixelSize.get()

    def setScannedPixelSize(self, scannedPixelSize):
        """ Set scannedPixelSize and update samplingRate. """
        mag = self._acquisition.getMagnification()
        if mag is None:
            raise Exception("SetOfMicrographs: cannot set scanned pixel size "
                            "if Magnification is not set.")
        self._scannedPixelSize.set(scannedPixelSize)
        self._samplingRate.set((1e+4 * scannedPixelSize) / mag)


class MockSetOfParticles(MockSetOfImages):
    """ Represents a set of Particles.
    The purpose of this class is to separate the
    concepts of Micrographs and Particles, even if
    both are considered Images
    """
    ITEM_TYPE = MockParticle
    REP_TYPE = MockParticle

    def __init__(self, **kwargs):
        MockSetOfImages.__init__(self, **kwargs)
        self._coordsPointer = pwobj.Pointer()

    def hasCoordinates(self):
        return self._coordsPointer.hasValue()

    def getCoordinates(self):
        """ Returns the SetOfCoordinates associated with
        this SetOfParticles"""
        return self._coordsPointer.get()

    def setCoordinates(self, coordinates):
        """ Set the SetOfCoordinates associates with
        this set of particles.
         """
        self._coordsPointer.set(coordinates)

    def copyInfo(self, other):
        """ Copy basic information (voltage, spherical aberration and
        sampling rate) from other set of micrographs to current one.
        """
        MockSetOfImages.copyInfo(self, other)
        self.setHasCTF(other.hasCTF())


class MockCoordinate(MockObject):
    """This class holds the (x,y) position and other information
    associated with a coordinate"""
    def __init__(self, **kwargs):
        MockObject.__init__(self, **kwargs)
        self._micrographPointer = pwobj.Pointer(objDoStore=False)
        self._x = pwobj.Integer(kwargs.get('x', None))
        self._y = pwobj.Integer(kwargs.get('y', None))
        self._micId = pwobj.Integer()
        self._micName = pwobj.String()

    def getX(self):
        return self._x.get()

    def setX(self, x):
        self._x.set(x)

    def shiftX(self, shiftX):
        self._x.sum(shiftX)

    def getY(self):
        return self._y.get()

    def setY(self, y):
        self._y.set(y)

    def shiftY(self, shiftY):
        self._y.sum(shiftY)

    def scale(self, factor):
        """ Scale both x and y coordinates by a given factor.
        """
        self._x.multiply(factor)
        self._y.multiply(factor)

    def getPosition(self):
        """ Return the position of the coordinate as a (x, y) tuple.
        mode: select if the position is the center of the box
        or in the top left corner.
        """
        return self.getX(), self.getY()

    def setPosition(self, x, y):
        self.setX(x)
        self.setY(y)

    def getMicrograph(self):
        """ Return the micrograph object to which
        this coordinate is associated.
        """
        return self._micrographPointer.get()

    def setMicrograph(self, micrograph):
        """ Set the micrograph to which this coordinate belongs. """
        self._micrographPointer.set(micrograph)
        self._micId.set(micrograph.getObjId())
        self._micName.set(micrograph.getMicName())

    def copyInfo(self, coord):
        """ Copy information from other coordinate. """
        self.setPosition(*coord.getPosition())
        self.setObjId(coord.getObjId())
        self.setBoxSize(coord.getBoxSize())

    def getMicId(self):
        return self._micId.get()

    def setMicId(self, micId):
        self._micId.set(micId)

    def invertY(self):
        if not self.getMicrograph() is None:
            dims = self.getMicrograph().getDim()
            height = dims[1]
            self.setY(height - self.getY())
        # else: error TODO

    def setMicName(self, micName):
        self._micName.set(micName)

    def getMicName(self):
        return self._micName.get()


class SetOfCoordinates(MockSet):
    """ Encapsulate the logic of a set of particles coordinates.
    Each coordinate has a (x,y) position and is related to a Micrograph
    The SetOfCoordinates can also have information about TiltPairs.
    """
    ITEM_TYPE = MockCoordinate

    def __init__(self, **kwargs):
        MockSet.__init__(self, **kwargs)
        self._micrographsPointer = pwobj.Pointer()
        self._boxSize = pwobj.Integer()

    def getBoxSize(self):
        """ Return the box size of the particles.
        """
        return self._boxSize.get()

    def setBoxSize(self, boxSize):
        """ Set the box size of the particles. """
        self._boxSize.set(boxSize)

    def iterMicrographs(self):
        """ Iterate over the micrographs set associated with this
        set of coordinates.
        """
        return self.getMicrographs()

    def iterMicrographCoordinates(self, micrograph):
        """ Iterates over the set of coordinates belonging to that micrograph.
        """
        pass

    def iterCoordinates(self, micrograph=None):
        """ Iterate over the coordinates associated with a micrograph.
        If micrograph=None, the iteration is performed over the whole
        set of coordinates.
        """
        if micrograph is None:
            micId = None
        elif isinstance(micrograph, int):
            micId = micrograph
        elif isinstance(micrograph, MockMicrograph):
            micId = micrograph.getObjId()
        else:
            raise Exception('Invalid input micrograph of type %s'
                            % type(micrograph))

        # Iterate over all coordinates if micId is None,
        # otherwise use micId to filter the where selection
        coordWhere = '1' if micId is None else '_micId=%d' % micId

        for coord in self.iterItems(where=coordWhere):
            yield coord

    def getMicrographs(self):
        """ Returns the SetOfMicrographs associated with
        this SetOfCoordinates"""
        return self._micrographsPointer.get()

    def setMicrographs(self, micrographs):
        """ Set the micrographs associated with this set of coordinates.
        Params:
            micrographs: Either a SetOfMicrographs object or a pointer to it.
        """
        if micrographs.isPointer():
            self._micrographsPointer.copy(micrographs)
        else:
            self._micrographsPointer.set(micrographs)
        
    def getFiles(self):
        filePaths = set()
        filePaths.add(self.getFileName())
        return filePaths

    def __str__(self):
        """ String representation of a set of coordinates. """
        if self._boxSize.hasValue():
            boxSize = self._boxSize.get()
            boxStr = ' %d x %d' % (boxSize, boxSize)
        else:
            boxStr = 'No-Box'
        s = "%s (%d items, %s%s)" % (self.getClassName(), self.getSize(),
                                     boxStr, self._appendStreamState())

        return s

    def copyInfo(self, other):
        """ Copy basic information (boxsize)
                from other set of coordinates to current one"""
        self.copyAttributes(other, '_boxSize')

