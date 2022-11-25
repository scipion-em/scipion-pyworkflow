#!/usr/bin/env python
# **************************************************************************
# *
# * Authors:     I. Foche Perez (ifoche@cnb.csic.es)
# *              J. Burguet Castell (jburguet@cnb.csic.es)
# *
# * Unidad de Bioinformatica of Centro Nacional de Biotecnologia, CSIC
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
Scipion data synchronization.

Get(put) tests data, from(to) the server to(from) the $SCIPION_TESTS folder.
"""
import logging
logger = None

import sys
import os
from os.path import join, isdir, exists, relpath, dirname
from subprocess import call
import time
import argparse
import hashlib
import getpass
from urllib.request import urlopen, urlretrieve

import pyworkflow as pw
from pyworkflow.utils import redB, red, green, yellow


def main():

    #Configure logging
    logging.basicConfig(level=pw.Config.SCIPION_LOG_LEVEL, format=pw.Config.SCIPION_LOG_FORMAT)
    global logger
    logger = logging.getLogger(__name__)

    # Get arguments.
    args = get_parser().parse_args()

    # Dispatch the easy cases first (list and check), and then take care of
    # the more complex ones.
    if args.list:
        listDatasets(args.url)
        sys.exit(0)

    if args.check:
        if not args.datasets:
            datasets = [x.decode("utf-8").strip('./\n') for x in urlopen('%s/MANIFEST' % args.url)]
        else:
            datasets = args.datasets

        logger.info('Checking %s at %s.' % (' '.join(datasets), args.url))

        all_uptodate = True
        for dataset in datasets:
            all_uptodate &= check(dataset, url=args.url, verbose=args.verbose)
        if all_uptodate:
            logger.info('All datasets are up-to-date.')
            sys.exit(0)
        else:
            logger.error('Some datasets are not updated.')
            sys.exit(1)

    if not args.datasets:
        sys.exit('At least --list, --check or datasets needed.\n'
                 'Run with --help for more info.')

    logger.info('Selected datasets: %s' % yellow(' '.join(args.datasets)))

    testFolder = pw.Config.SCIPION_TESTS

    if args.format:
        for dataset in args.datasets:
            datasetFolder = join(testFolder, dataset)
            logger.info('Formatting %s (creating MANIFEST file)' % dataset)

            if not exists(datasetFolder):
                sys.exit('ERROR: %s does not exist in datasets folder %s.' %
                         (dataset, testFolder))
            createMANIFEST(datasetFolder)
        sys.exit(0)

    if args.download:
        # Download datasets.
        try:
            for dataset in args.datasets:
                if exists(join(testFolder, dataset)):
                    logger.info('Local copy of dataset %s detected.' % dataset)
                    logger.info('Checking for updates...')
                    update(dataset, url=args.url, verbose=args.verbose)
                else:
                    logger.info('Dataset %s not in local machine. '
                          'Downloading...' % dataset)
                    download(dataset, url=args.url, verbose=args.verbose)
        except IOError as e:
            logger.warning('%s' % e)
            if e.errno == 13:  # permission denied
                logger.warning('Maybe you need to run as the user that '
                      'did the global installation?')
            sys.exit(1)
        sys.exit(0)

    if args.upload:
        # Upload datasets.
        for dataset in args.datasets:
            try:
                upload(dataset, login=args.login,
                       remoteFolder=args.remotefolder, delete=args.delete)
            except Exception as e:
                logger.error('Error when uploading dataset %s: %s' % (dataset, e))
                if ask() != 'y':
                    sys.exit(1)
        sys.exit(0)

    # If we get here, we did not use the right arguments. Show a little help.
    get_parser().print_usage()


def get_parser():
    """ Return the argparse parser, so we can get the arguments """

    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group()
    g.add_argument('--download', action='store_true', help="Download dataset.")
    g.add_argument(
        '--upload', action='store_true',
        help=("Upload local dataset to the server. The dataset name must be "
              "the name of its folder relative to the $%s folder." % pw.SCIPION_TESTS))
    g.add_argument(
        '--list', action='store_true',
        help=('List local datasets (from $%s) and remote ones '
              '(remote url can be specified with --url).' % pw.SCIPION_TESTS))
    g.add_argument(
        '--format', action='store_true',
        help='Create a MANIFEST file with checksums in the datasets folders.')
    add = parser.add_argument  # shortcut
    add('datasets', metavar='DATASET', nargs='*', help='Name of a dataset.')
    add('--delete', action='store_true',
        help=('When uploading, delete any remote files in the dataset not '
              'present in local. It leaves the remote scipion data directory '
              'as it is in the local one. Dangerous, use with caution.'))
    add('-u', '--url', default=pw.Config.SCIPION_URL_TESTDATA,
        help='URL where remote datasets will be looked for.')
    add('--check', action='store_true',
        help='See if there is any remote dataset not in sync with locals.')
    add('-l', '--login', default='scipion@scipion.cnb.csic.es', help='ssh login string. For upload')
    add('-rf', '--remotefolder', default='scipionfiles/downloads/scipion/data/tests',
        help='remote folder to put the dataset there. For upload.')
    add('-v', '--verbose', action='store_true', help='Print more details.')

    return parser


def listDatasets(url):
    """ Print a list of local and remote datasets """

    tdir = pw.Config.SCIPION_TESTS
    print("Local datasets in %s" % yellow(tdir))
    for folder in sorted(os.listdir(tdir)):
        if isdir(join(tdir, folder)):
            if exists(join(tdir, folder, 'MANIFEST')):
                print("  * %s" % folder)
            else:
                print("  * %s (not in dataset format)" % folder)

    try:
        print("\nRemote datasets in %s" % yellow(url))
        for line in sorted(urlopen('%s/MANIFEST' % url)):
            print("  * %s" % line.decode("utf-8").strip('./\n'))
    except Exception as e:
        logger.info("Error reading %s (%s)" % (url, e))


def check(dataset, url, verbose=False, updateMANIFEST=False):
    """ See if our local copy of dataset is the same as the remote one.
    Return True if it is (if all the checksums are equal), False if not.
    """
    def vlog(txt): logger.info(txt) if verbose else None  # verbose log

    vlog("Checking dataset %s ... " % dataset)

    if updateMANIFEST:
        createMANIFEST(join(pw.Config.SCIPION_TESTS, dataset))
    else:
        vlog("(not updating local MANIFEST) ")

    try:
        md5sRemote = dict(x.decode("utf-8").split() for x in
                          urlopen('%s/%s/MANIFEST' % (url, dataset)))

        md5sLocal = dict(x.split() for x in
                         open('%s/MANIFEST' %
                              join(pw.Config.SCIPION_TESTS, dataset)))
        if md5sRemote == md5sLocal:
            vlog("\tlooks up-to-date\n")
            return True
        else:
            vlog("\thas differences\n")
            flocal = set(md5sLocal.keys())
            fremote = set(md5sRemote.keys())

            def show(txt, lst):
                if lst:
                    vlog("  %s: %s\n" % (txt, ' '.join(lst)))
            show("Local files missing in the server", flocal - fremote)
            show("Remote files missing locally", fremote - flocal)
            show("Files with differences", [f for f in fremote & flocal
                                            if md5sLocal[f] != md5sRemote[f]])
            return False
    except Exception as e:
        logger.error("Can't check dataset %s." % dataset, exc_info=e)
        return False


def download(dataset, destination=None, url=None, verbose=False):
    """ Download all the data files mentioned in url/dataset/MANIFEST """
    # Get default values for variables if we got None.
    destination = destination or pw.Config.SCIPION_TESTS

    # First make sure that we ask for a known dataset.
    if dataset not in [x.decode('utf-8').strip('./\n') for x in urlopen('%s/MANIFEST' % url)]:
        logger.info("Unknown dataset: %s" % red(dataset))
        logger.info("Use --list to see the available datasets.")
        return

    # Retrieve the dataset's MANIFEST file.
    # It contains a list of "file md5sum" of all files included in the dataset.
    datasetFolder = join(destination, dataset)
    os.makedirs(datasetFolder)
    manifest = join(destination, dataset, 'MANIFEST')
    try:
        if verbose:
            logger.info("Retrieving MANIFEST file")
        open(manifest, 'wb').writelines(
            urlopen('%s/%s/MANIFEST' % (url, dataset)))
    except Exception as e:
        logger.info("ERROR reading %s/%s/MANIFEST (%s)" % (url, dataset, e))
        return

    # Now retrieve all of the files mentioned in MANIFEST, and check their md5.
    logger.info('Fetching files of dataset "%s"...' % dataset)
    lines = open(manifest).readlines()
    done = 0.0  # fraction already done
    inc = 1.0 / len(lines)  # increment, how much each iteration represents
    for line in lines:
        fname, md5Remote = line.strip().split()
        fpath = join(datasetFolder, fname)
        try:
            # Download content and create file with it.
            if not isdir(dirname(fpath)):
                os.makedirs(dirname(fpath))
            open(fpath, 'wb').writelines(
                urlopen('%s/%s/%s' % (url, dataset, fname)))

            md5 = md5sum(fpath)
            assert md5 == md5Remote, \
                "Bad md5. Expected: %s Computed: %s" % (md5Remote, md5)

            done += inc
            if verbose:
                logger.info(redB("%3d%% " % (100 * done)) + fname)
            else:
                sys.stdout.write(redB("#") * (int(50*done)-int(50*(done-inc))))
                sys.stdout.flush()
        except Exception as e:
            logger.info("\nError in %s (%s)" % (fname, e))
            logger.info("URL: %s/%s/%s" % (url, dataset, fname))
            logger.info("Destination: %s" % fpath)
            if ask("Continue downloading? (y/[n]): ", ['y', 'n', '']) != 'y':
                return


def update(dataset, workingCopy=None, url=None, verbose=False):
    """ Update local dataset with the contents of the remote one.
    It compares the md5 of remote files in url/dataset/MANIFEST with the
    ones in workingCopy/dataset/MANIFEST, and downloads only when necessary.
    """
    # Get default values for variables if we got None.
    workingCopy = workingCopy or pw.Config.SCIPION_TESTS

    # Verbose log
    def vlog(txt): logger.info(txt) if verbose else None

    # Read contents of *remote* MANIFEST file, and create a dict {fname: md5}
    manifest = urlopen('%s/%s/MANIFEST' % (url, dataset)).readlines()
    md5sRemote = dict(x.decode("utf-8").strip().split() for x in manifest)

    # Update and read contents of *local* MANIFEST file, and create a dict
    datasetFolder = join(workingCopy, dataset)
    try:
        last = max(os.stat(join(datasetFolder, x)).st_mtime for x in md5sRemote)
        t_manifest = os.stat(join(datasetFolder, 'MANIFEST')).st_mtime
        assert t_manifest > last and time.time() - t_manifest < 60*60*24*7
    except (OSError, IOError, AssertionError) as e:
        logger.info("Regenerating local MANIFEST...")
        createMANIFEST(datasetFolder)
    md5sLocal = dict(x.strip().split() for x in open(join(datasetFolder, 'MANIFEST')))

    # Check that all the files mentioned in MANIFEST are up-to-date
    logger.info("Verifying MD5s...")

    filesUpdated = 0  # number of files that have been updated
    taintedMANIFEST = False  # can MANIFEST be out of sync?
    downloadingPrinted = False
    for fname in md5sRemote:
        fpath = join(datasetFolder, fname)
        try:
            if exists(fpath) and md5sLocal[fname] == md5sRemote[fname]:
                vlog("\r  %s  %s\n" % (green("OK"), fname))
                pass  # just to emphasize that we do nothing in this case
            else:
                if not downloadingPrinted:
                    verboseMsg = " Next time use -v for more details." if not verbose else ""
                    logger.info("%s differs. Downloading new version.%s" % (fname, verboseMsg))

                vlog("\r  %s  %s  (downloading... " % (red("XX"), fname))
                if not isdir(dirname(fpath)):
                    os.makedirs(dirname(fpath))

                urlretrieve('%s/%s/%s' % (url, dataset, fname)
                            , fpath)

                vlog("done)")
                filesUpdated += 1
        except Exception as e:
            logger.error("Couldn't update %s." % fname, exc_info= e)
            taintedMANIFEST = True  # if we don't update, it can be wrong

    logger.info("...done. Updated files: %d" % filesUpdated)

    # Save the new MANIFEST file in the folder of the downloaded dataset
    if filesUpdated > 0:
        open(join(datasetFolder, 'MANIFEST'), 'w').writelines(md5sRemote)

    if taintedMANIFEST:
        logger.info("Some files could not be updated. Regenerating local MANIFEST ...")
        createMANIFEST(datasetFolder)


def upload(dataset, login, remoteFolder, delete=False):
    """ Upload a dataset to our repository """

    localFolder = join(pw.Config.SCIPION_TESTS, dataset)

    if not exists(localFolder):
        sys.exit("ERROR: local folder %s does not exist." % localFolder)

    logger.info("Warning: Uploading, please BE CAREFUL! This can be dangerous.")
    logger.info('You are going to be connected to "%s" to write in folder '
          '"%s" the dataset "%s".' % (login, remoteFolder, dataset))
    if ask() == 'n':
        return

    # First make sure we have our MANIFEST file up-to-date
    logger.info("Updating local MANIFEST file with MD5 info...")
    createMANIFEST(localFolder)

    # Upload the dataset files (with rsync)
    logger.info("Uploading files...")
    call(['rsync', '-rlv', '--chmod=a+r', localFolder,
          '%s:%s' % (login, remoteFolder)] + (['--delete'] if delete else []))

    # Regenerate remote MANIFEST (which contains a list of datasets)
    logger.info("Regenerating remote MANIFEST file...")
    call(['ssh', login,
          'cd %s && find -type d -mindepth 1 -maxdepth 1 > MANIFEST' % remoteFolder])
    # This is a file that just contains the name of the directories
    # in remoteFolder. Nothing to do with the MANIFEST files in
    # the datasets, which contain file names and md5s.

    # Leave a register (log file)
    logger.info("Logging modification attempt in modifications.log ...")
    log = """++++
Modification to %s dataset made at
%s
by %s at %s
----""" % (dataset, time.asctime(), getpass.getuser(), ' '.join(os.uname()))
    call(['ssh', login,
          'echo "%s" >> %s' % (log, join(remoteFolder, 'modifications.log'))])
    logger.info("...done.")


def createMANIFEST(path):
    """ Create a MANIFEST file in path with the md5 of all files below """

    with open(join(path, 'MANIFEST'), 'w') as manifest:
        for root, dirs, files in os.walk(path):
            for filename in set(files) - {'MANIFEST'}:  # all but ourselves
                fn = join(root, filename)  # file to check
                logger.info("Calculating md5 for local %s ... " % filename)
                manifest.write('%s %s\n' % (relpath(fn, path), md5sum(fn)))
                logger.info(green("DONE!"))

def md5sum(fname):
    """ Return the md5 hash of file fname """

    mhash = hashlib.md5()
    with open(fname, 'rb') as f:
        for chunk in iter(lambda: f.read(128 * mhash.block_size), b""):
            mhash.update(chunk)
    return mhash.hexdigest()


def ask(question="Continue? (y/n): ", allowed=None):
    """ Ask the question until it returns one of the allowed responses """

    while True:
        ans = input(question)
        if ans.lower() in (allowed if allowed else ['y', 'n']):
            return ans


if __name__ == "__main__":
    main()
