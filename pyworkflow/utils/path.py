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
This module contains the PATH related utilities
inside the utils module
"""


import os
import shutil
import sys
from glob import glob
import datetime

from pyworkflow import SCIPION_SCRATCH, DOCSITEURLS, ASCII_COLOR_2_TKINTER
from pyworkflow.exceptions import PyworkflowException
from pyworkflow.config import Config

ROOT = "/"


def findFileRecursive(filename, path):
    """
    Finds a file/folder in a single path recursively

    :param filename: Name (myfile.txt) of the file to look for.
    :param path: folder to start the search from.
    :return: The absolute path to the 'filename' found or None if not found.
    """
    for root, dirs, files in os.walk(path):
        if filename in files or filename in dirs:
            return os.path.join(root, filename)
    return None   
        

def findFile(filename, *paths, recursive=False):
    """
    Search if a file/folder is present in any of the paths provided.

    :param filename: Name (myfile.txt) of the file to look for.
    :param paths: N number of folders to look at.
    :param recursive: If True it will iterate into the subfolders.
    :return: None if nothing is found.
    """

    if filename:
        for p in paths:
            fn = os.path.join(p, filename)
            if os.path.exists(fn):
                return fn
            if recursive:
                f = findFileRecursive(filename, p)
                if f:
                    return f
    return None


def findRootFrom(referenceFile, searchFile):
    """ This method will find a path (root) from 'referenceFile'
    from which the 'searchFile' os.path.exists. 
    A practical example of 'referenceFile' is a metadata file
    and 'searchFile' is an image to be found from the metadata.
    Return None if the path is not found.
    """
    absPath = os.path.dirname(os.path.abspath(referenceFile))
    
    while absPath is not None and absPath != '/':
        if os.path.exists(os.path.join(absPath, searchFile)):
            return absPath
        absPath = os.path.dirname(absPath)
        
    return None   


def getParentFolder(path):
    """ Returns the absolute parent folder of a file or folder. Work for
    folders that ens with "/" which dirname can't"""
    return os.path.dirname(os.path.abspath(path))


def replaceExt(filename, newExt):
    """ Replace the current path extension(from last .)
    with a new one. The new one should not contains the ."""
    return os.path.splitext(filename)[0] + '.' + newExt


def replaceBaseExt(filename, newExt):
    """ Replace the current basename extension(from last .)
    with a new one. The new one should not contains the .
    """
    return replaceExt(os.path.basename(filename), newExt)


def removeBaseExt(filename):
    """Take the basename of the filename and remove extension"""
    return removeExt(os.path.basename(filename))


def removeExt(filename):
    """ Remove extension from basename """
    return os.path.splitext(filename)[0]


def joinExt(*extensions):
    """ Join several path parts with a ."""
    return '.'.join(extensions)


def getExt(filePath):
    """ Return the extension given a file. """
    return os.path.splitext(filePath)[1]


def cleanPath(*paths):
    """ Remove a list of paths, either folders or files"""
    for p in paths:
        if os.path.exists(p):
            if os.path.isdir(p):
                if os.path.islink(p):
                    os.remove(p)
                else:
                    shutil.rmtree(p)
            else:
                os.remove(p)


def cleanPattern(pattern):
    """ Remove all files that match the pattern. """
    files = glob(pattern)
    cleanPath(*files)


def copyPattern(pattern, destFolder):
    """ Copy all files matching the pattern to the given destination folder."""
    for file in glob(pattern):
        copyFile(file, destFolder)


def makePath(*paths):
    """ Create a list of paths if they don't os.path.exists.
    Recursively create all folder needed in a path.
    If a path passed is a file, only the directory will be created.
    """
    for p in paths:
        if not os.path.exists(p) and len(p):
            os.makedirs(p)


def makeTmpPath(protocol):
    """
    Create the scratch folder if SCIPION_SCRATCH variable is defined into the
    Scipion config, i.o.c create tmp folder
    """
    tmpPath = protocol._getTmpPath()
    if not os.path.exists(tmpPath) and len(tmpPath):
        scratchPath = Config.SCIPION_SCRATCH

        if scratchPath is None:  # Case when SCIPION_SCRATCH doesn't exist. TMP folder is created
            os.makedirs(tmpPath)
        else:
            try:
                project = protocol.getProject()
                folderId = "_".join([project.getShortName(),project.getProtWorkingDir(protocol)])
                tmpScratchFolder = os.path.join(scratchPath, folderId)
                if os.path.exists(tmpScratchFolder):
                    cleanPath(tmpScratchFolder)
                os.makedirs(tmpScratchFolder)  # Create scratch folder
                createAbsLink(tmpScratchFolder, tmpPath)  # Create a sym link

            except Exception as e:
                raise PyworkflowException("Couldn't create the temporary folder %s at:\n %s\nPlease, review %s variable." %
                                (folderId, scratchPath, SCIPION_SCRATCH), url=DOCSITEURLS.CONFIG_SECTION % "scratch-folder") from e


def makeFilePath(*files):
    """ Make the path to ensure that files can be written. """
    makePath(*[os.path.dirname(f) for f in files])


def missingPaths(*paths):
    """ Check if the list of paths os.path.exists.
    Will return the list of missing files,
    if the list is empty means that all path os.path.exists
    """
    return [p for p in paths if not os.path.exists(p)]


def getHomePath(user=''):
    """Return the home path of a give user."""
    return os.path.expanduser("~" + user)


def expandPattern(pattern, vars=True, user=True):
    """ Expand environment vars and user from a given pattern. """
    if vars:
        pattern = os.path.expandvars(pattern)
    if user:
        pattern = os.path.expanduser(pattern)
    return pattern


def getFiles(folderPath):
    """
    Gets all files of given folder and it subfolders.
    folderPath -- Folder path to get files.
    returns -- Set with all folder files.
    """
    filePaths = set()
    for path, dirs, files in os.walk(folderPath):
        for f in files:
            filePaths.add(os.path.join(path, f))
    return filePaths


def copyTree(source, dest):
    """
    Wrapper around the shutil.copytree, but allowing
    that the dest folder also os.path.exists.
    """
    if not os.path.exists(dest):
        shutil.copytree(source, dest, symlinks=True)
    else:
        for f in os.listdir(source):
            fnPath = os.path.join(source, f)
            if os.path.isfile(fnPath):
                shutil.copy(fnPath, dest)
            elif os.path.isdir(fnPath):
                copyTree(fnPath, os.path.join(dest, f))


def moveTree(src, dest):
    copyTree(src, dest)
    cleanPath(src)


def copyFile(source, dest):
    """ Shortcut to shutil.copy. """
    shutil.copy(source, dest)


def moveFile(source, dest):
    """ Move file from source to dest. """
    copyFile(source, dest)
    cleanPath(source)


def createLink(source, dest):
    """ Creates a relative link to a given file path. 
    Try to use common path for source and dest to avoid errors. 
    Different relative paths may exist since there are different valid paths
    for a file, it depends on the current working dir path"""
    if os.path.islink(dest):
        os.remove(dest)
        
    if os.path.exists(dest):
        raise Exception('Destination %s os.path.exists and is not a link'
                        % dest)
    sourcedir = getParentFolder(source)
    destdir = getParentFolder(dest)
    relsource = os.path.join(os.path.relpath(sourcedir, destdir),
                             os.path.basename(source))
    os.symlink(relsource, dest)


def createAbsLink(source, dest):
    """ Creates a link to a given file path"""
    if os.path.islink(dest):
        os.remove(dest)
        
    if os.path.exists(dest):
        raise Exception('Destination %s os.path.exists and is not a link' % dest)

    os.symlink(source, dest)


def getLastFile(pattern):
    """ Return the last file matching the pattern. """
    files = glob(pattern)
    if len(files):
        files.sort()
        return files[-1]
    return None


def commonPath(*paths):
    """ Return the common longest prefix path.
    It uses the python os.path.commonprefix and 
    then the direname over it since the former is
    implemented in char-by-char base.
    """
    return os.path.dirname(os.path.commonprefix(*paths))



def renderTextFile(fname, add, offset=0, lineNo=0, numberLines=True,
                   maxSize=400, headSize=40, tailSize=None, notifyLine=None, errors='strict'):
    """
    Call callback function add() on each fragment of text from file fname,
    delimited by lines and/or color codes.

    :param add: callback function with signature (txt, tag='normal')
    :param offset: byte offset - we start reading the file from there
    :param lineNo: lines will be numbered from this value on
    :param numberLines: whether to prepend the line numbers

    """
    textfile = open(fname, encoding='utf-8', errors=errors)
    size = (os.stat(fname).st_size - offset) / 1024  # in kB

    for line in iterBigFile(textfile, offset, size,
                            maxSize, headSize, tailSize):
        if line is not None:
            lineNo += 1
            if notifyLine is not None:
                notifyLine(line)
            renderLine(line, add, lineNo, numberLines)
        else:
            add("""\n
    ==> Too much data to read (%d kB) -- %d kB omitted
    ==> Click on """ % (size, size - headSize - (tailSize or headSize)))
            add(fname, 'link:%s' % fname)
            add(' to open it with the default viewer\n\n')
            if numberLines:
                add('    ==> Line numbers below are not '
                    'in sync with the input data\n\n')

    offset = textfile.tell()  # save last position in file
    textfile.close()

    return offset, lineNo


def renderLine(line, add, lineNo=1, numberLines=True):
    """
    Find all the fragments of formatted text in line and call
    add(fragment, tag) for each of them.
    """
    # Prepend line number
    if numberLines and lineNo:
        add('%05d:' % lineNo, 'cyan')
        add('   ')

    # iter 1\riter 2\riter 3  -->  iter 3
    if '\r' in line:
        line = line[line.rfind('\r')+1:]  # overwriting!

    # Find all console escape codes and use the appropriate tag instead.
    pos = 0  # current position in the line we are parsing
    attribute = None
    while True:
        # line looks like:
        #   'blah blah \x1b[{attr1};...;{attrn}mTEXT\x1b[0m blah blah'
        # where {attrn} is the color code (31 is red, for example). See
        # http://www.termsys.demon.co.uk/vtansi.htm#colors
        start = line.find('\x1b[', pos)
        if start < 0:  # no more escape codes, just add the remaining text
            add(line[pos:], attribute)
            break

        add(line[pos:start], attribute)
        end = line.find('m', start+2)
        if end < 0:  # an escape code interrupted by newline... weird
            break
        code = line[start+2:end]

        # See what attribute to use from now on, and update pos
        if code == '0':
            attribute = None
        else:
            attribute = ASCII_COLOR_2_TKINTER.get(code[-2:], None)
        pos = end + 1  # go to the character next to "m", the closing char


def iterBigFile(textfile, offset=0, size=None,
                maxSize=400, headSize=40, tailSize=None):
    """
    Yield lines from file textfile. If the size to read is bigger
    than maxSize then yield the first lines until headSize bytes, then
    yield None, then yield the last lines from tailSize bytes to the end.
    """
    if size is None:
        # Size in kB of the part of the file that we will read
        textfile.seek(0, 2)
        sizeKb = (textfile.tell() - offset) / 1024
    else:
        sizeKb = size

    headSizeB = headSize * 1024
    tailSizeB = (tailSize or headSize) * 1024

    textfile.seek(offset)
    # If the size is bigger than the max that we want to read (in kB).
    if 0 < maxSize < sizeKb:
        # maxSize <= 0 means we just want to read it all and not enter here.
        for line in textfile.read(headSizeB).split('\n'):
            yield line + '\n'
        yield None  # Special result to mark omitting lines
        textfile.seek(sizeKb*1024-tailSizeB)  # ready to show the last bytes

    # Add the remaining lines (from our last offset)
    for line in textfile:
        yield line


def createUniqueFileName(fn):
    """
    This function creates a file name that is similar to the original
    by adding a unique numeric suffix. check   NamedTemporaryFile
    from tempfile for alternatives
    """
    if not os.path.os.path.exists(fn):
        return fn

    path, name = os.path.split(fn)
    name, ext = os.path.splitext(name)

    make_fn = lambda i: os.path.join(path, '%s_tmp_%d_%s' % (name, i, ext))

    for i in range(2, sys.maxsize):
        uni_fn = make_fn(i)
        if not os.path.os.path.exists(uni_fn):
            return uni_fn

    return None


def getFileSize(fn):
    """ Shortcut to inspect the size of a file or a folder. """

    if not os.path.exists(fn):
        return  0

    elif os.path.isdir(fn):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(fn):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return total_size

    else:
        return os.path.getsize(fn)


def getFileLastModificationDate(fn):
    """ Returns the last modification date of a file or None
    if it doesn't exist. """
    if os.path.exists(fn):
        ts = os.path.getmtime(fn)
        return datetime.datetime.fromtimestamp(ts)
    else:
        print(fn + " does not exist!!. Can't check last modification date.")
        return None
