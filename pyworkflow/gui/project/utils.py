# **************************************************************************
# *
# * Authors:     Pablo Conesa (pconesa@cnb.csic.es)
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
import datetime
import platform
import abc
from abc import ABC

from pyworkflow.gui.project.constants import STATUS_COLORS, WARNING_COLOR
from pyworkflow.protocol import STATUS_FAILED
from pyworkflow.viewer import ProtocolViewer


def getStatusColorFromNode(node):
    # If it is a run node (not PROJECT)
    return getStatusColorFromRun(node.run)


def getStatusColorFromRun(prot):
    """ Returns the color associated with the status. """
    if prot:
        if prot.hasSummaryWarnings():
            return WARNING_COLOR
        else:
            return getStatusColor(prot.status.get(STATUS_FAILED))
    else:
        return getStatusColor()


def getStatusColor(status=None, default='#ADD8E6'):
    """
    Parameters
    ----------
    status status of the protocol

    Returns the color associated with he status
    -------

    """
    return STATUS_COLORS[status] if status else default

# OS dependent behaviour. Add any OS dependent method here and later we might move
# or refactor this to a class or something else


class OSHandler(abc.ABC):
    """ Abstract class: Handler for OS specific actions"""
    def maximizeWindow(root):
        pass


class LinuxHandler(OSHandler, ABC):

    def maximizeWindow(root):
        root.attributes("-zoomed", True)


class MacHandler(OSHandler, ABC):

    def maximizeWindow(root):
        root.state("zoomed")


class WindowsHandler(OSHandler, ABC):

    def maximizeWindow(root):
        root.state("zoomed")


class OS:
    _handler = None

    _handlers = {"Linux": LinuxHandler,
                 "Darwin": MacHandler,
                 "Windows": WindowsHandler}  # Until testing this on windows

    @staticmethod
    def getPlatform():
        return platform.system()

    @classmethod
    def handler(cls):
        if cls._handler is None:
            cls._handler = cls._handlers[cls.getPlatform()]

        return cls._handler

    @classmethod
    def getDistro(cls):
        return platform.os.uname().version


def isAFinalProtocol(v, k):
    if (issubclass(v, ProtocolViewer) or
            v.isBase() or v.isDisabled()):
        return False

    return v.__name__ == k


def inspectObj(object, filename, prefix='', maxDeep=5, inspectDetail=2, memoryDict=None):
    """ Creates a .CSV file in the filename path with
        all its members and recursively with a certain maxDeep,
        if maxDeep=0 means no maxDeep (until all members are inspected).

        inspectDetail can be:
         - 1: All attributes are shown
         - 2: All attributes are shown and iterable values are also inspected

        prefix and memoryDict will be updated in the recursive entries:
         - prefix is a compound of the two first columns (DEEP and Tree)
         - memoryDict is a dictionary with the memory address and an identifier
    """
    END_LINE = '\n'  # end of line char
    COL_DELIM = '\t'  # column delimiter
    INDENT_COUNTER = '/'  # character append in each indention (it's not written)

    NEW_CHILD = '  |------>  '  # new item indention
    BAR_CHILD = '  | ' + INDENT_COUNTER  # bar indention
    END_CHILD = ('       -- ' + COL_DELIM) * 4 + END_LINE  # Child ending
    column1 = '    - Name - ' + COL_DELIM
    column2 = '    - Type - ' + COL_DELIM
    column3 = '    - Value - ' + COL_DELIM
    column4 = '  - Memory Address -'

    #  Constants to distinguish the first, last and middle rows
    IS_FIRST = 1
    IS_LAST = -1
    IS_MIDDLE = 0

    memoryDict = memoryDict or {}

    def writeRow(name, value, prefix, posList=False):
        """ Writes a row item. """
        # we will avoid to recursively print the items wrote before
        #  (ie. with the same memory address), thus we store a dict with the
        #  addresses and the flag isNew is properly set
        if str(hex(id(value))) in memoryDict:
            memorySTR = memoryDict[str(hex(id(value)))]
            isNew = False
        else:
            # if the item is new, we save its memory address in the memoryDict
            #   and we pass the name and the line on the file as a reference.
            memorySTR = str(hex(id(value)))
            file = open(filename, 'r')
            lineNum = str(len(file.readlines()) + 1)
            file.close()
            nameDict = str(name)[0:15] + ' ...' if len(str(name)) > 25 else str(name)
            memoryDict[str(hex(id(value)))] = '>>> ' + nameDict + ' - L:' + lineNum
            isNew = True

        if posList:
            # if we have a List, the third column is 'pos/lenght'
            thirdCol = posList
        else:
            # else, we print the value avoiding the EndOfLine char (// instead)
            thirdCol = str(value).replace(END_LINE, ' // ')

        # we will print the indentation deep number in the first row
        indentionDeep = prefix.count(INDENT_COUNTER)
        deepStr = str(indentionDeep) + COL_DELIM

        # the prefix without the indentCounters is
        #   the tree to be printed in the 2nd row
        prefixToWrite = prefix.replace(INDENT_COUNTER, '')

        file = open(filename, 'a')
        file.write(deepStr + prefixToWrite + COL_DELIM +
                   str(name) + COL_DELIM +
                   str(type(value)) + COL_DELIM +
                   thirdCol + COL_DELIM +
                   memorySTR + END_LINE)
        file.close()

        return isNew

    def recursivePrint(value, prefix, isFirstOrLast):
        """ We print the childs items of tuples, lists, dicts and classes. """

        # if it's the last item, its childs has not the bar indention
        if isFirstOrLast == IS_LAST:  # void indention when no more items
            prefixList = prefix.split(INDENT_COUNTER)
            prefixList[-2] = prefixList[-2].replace('|', ' ')
            prefix = INDENT_COUNTER.join(prefixList)

        # recursive step with the new prefix and memory dict.
        inspectObj(value, filename, prefix + BAR_CHILD, maxDeep, inspectDetail,
                   memoryDict)

        if isFirstOrLast == IS_FIRST:
            deepStr = str(indentionDeep) + COL_DELIM
        else:
            # When it was not the first item, the deep is increased
            #   to improve the readability when filter
            deepStr = str(indentionDeep + 1) + COL_DELIM

        prefix = prefix.replace(INDENT_COUNTER, '') + COL_DELIM

        # We introduce the end of the child and
        #   also the next header while it is not the last
        file = open(filename, 'a')
        file.write(deepStr + prefix + END_CHILD)
        if isFirstOrLast != IS_LAST:
            # header
            file.write(deepStr + prefix +
                       column1 + column2 + column3 + column4 + END_LINE)
        file.close()

    def isIterable(obj):
        """ Returns true if obj is a tuple, list, dict or calls. """
        isTupleListDict = (isinstance(obj, tuple) or
                           isinstance(obj, dict) or
                           isinstance(obj, list)) and len(value) > 1

        # FIX ME: I don't know how to assert if is a class or not...
        isClass = str(type(obj))[1] == 'c'

        return isClass or (isTupleListDict and inspectDetail < 2)

    indentionDeep = prefix.count(INDENT_COUNTER)
    if indentionDeep == 0:
        prefix = ' - Root - '

        # dict with name and value pairs of the members
        if len(object) == 1:
            # if only one obj is passed in the input list,
            #   we directly inspect that obj.
            obj_dict = object[0].__dict__
            object = object[0]

        #  setting the header row
        treeHeader = ' - Print on ' + str(datetime.datetime.now())
        prefixHeader = '-DEEP-' + COL_DELIM + treeHeader + COL_DELIM
        col1 = '    - Name - (value for Lists and Tuples)' + COL_DELIM
        col3 = '    - Value - (Pos./Len for Lists and Tuples) ' + COL_DELIM

        #  writing the header row
        file = open(filename, 'w')
        file.write(prefixHeader + col1 + column2 + col3 + column4 + END_LINE)
        file.close()

        #  writing the root object
        writeRow(object.__class__.__name__, object, prefix)
        #  adding the child bar to the prefix
        prefix = '  ' + BAR_CHILD
    else:
        # firsts settings depending on the type of the obj
        if str(type(object))[1] == 'c':
            obj_dict = object.__dict__
        elif (isinstance(object, tuple) or
              isinstance(object, list)):
            column1 = '    - Value - ' + COL_DELIM
            column3 = '  - Pos./Len. - ' + COL_DELIM
        elif isinstance(object, dict):
            column1 = '    - Key - ' + COL_DELIM
            obj_dict = object
        else:  # if is not of the type above it not make sense to continue
            return

    indentionDeep = prefix.count(INDENT_COUNTER)
    deepStr = str(indentionDeep) + COL_DELIM
    isBelowMaxDeep = indentionDeep < maxDeep if maxDeep > 0 else True

    prefixToWrite = prefix.replace(INDENT_COUNTER, '') + COL_DELIM
    file = open(filename, 'a')
    file.write(deepStr + prefixToWrite +
               column1 + column2 + column3 + column4 + END_LINE)
    file.close()

    #  we update the prefix to put the NEW_CHILD string  ( |----> )
    prefixList = prefix.split(INDENT_COUNTER)
    prefixList[-2] = NEW_CHILD
    #  we return to the string structure
    #    with a certain indention if it's the root
    prefixToWrite = '  ' + INDENT_COUNTER.join(prefixList) if indentionDeep == 1 \
        else INDENT_COUNTER.join(prefixList)

    isNew = True
    if str(type(object))[1] == 'c' or isinstance(object, dict):
        counter = 0
        for key, value in obj_dict.items():
            counter += 1
            # write the variable
            isNew = writeRow(key, value, prefixToWrite)

            # managing the extremes of the loop
            if counter == 1:
                isFirstOrLast = IS_FIRST
            elif counter == len(obj_dict):
                isFirstOrLast = IS_LAST
            else:
                isFirstOrLast = IS_MIDDLE

            # show attributes for objects and items for lists and tuples
            if isBelowMaxDeep and isNew and isIterable(value):
                recursivePrint(value, prefix, isFirstOrLast)
    else:
        for i in range(0, len(object)):
            # write the variable
            isNew = writeRow(object[i], object[i], prefixToWrite,
                             str(i + 1) + '/' + str(len(object)))

            # managing the extremes of the loop
            if i == 0:
                isFirstOrLast = IS_FIRST
            elif len(object) == i + 1:
                isFirstOrLast = IS_LAST
            else:
                isFirstOrLast = IS_MIDDLE

            # show attributes for objects and items for lists and tuples
            if isBelowMaxDeep and isNew and isIterable(object[i]):
                recursivePrint(object[i], prefix, isFirstOrLast)

