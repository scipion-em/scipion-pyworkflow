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
This modules contains classes required for the workflow
execution and tracking like: Step and Protocol
"""

# ------------------ Constants values -----------------------------------------

# Possible status of a protocol run, used mainly to monitor progress

STATUS_SAVED = "saved"  # Parameters saved for later use
STATUS_LAUNCHED = "launched"  # launched to queue system, only useful for protocols
STATUS_NEW = "new"
STATUS_RUNNING = "running"    # currently executing
STATUS_FAILED = "failed"      # it run and failed
STATUS_FINISHED = "finished"  # successfully finished
STATUS_ABORTED = "aborted"
STATUS_INTERACTIVE = "interactive"    # waiting for user interaction
STATUS_WAITING = "waiting"            # following status is used for streaming only
# Allow to schedule jobs not ready for running yet
STATUS_SCHEDULED = "scheduled"

ACTIVE_STATUS = [STATUS_LAUNCHED, STATUS_RUNNING, STATUS_INTERACTIVE,
                 STATUS_SCHEDULED]

# Execution modes
MODE_RESUME = 0    # Try to starting at the first changed step, skipping unchanged ones
MODE_RESTART = 1   # Restart the protocol from the beginning, deleting all previous results
MODE_CONTINUE = 2  # Continue from specific step, not widely used //DEPRECATED.
# JMRT: We now use 'Continue' label instead of 'Resume' which is more intuitive for users.
MODE_CHOICES = ('Continue', 'Restart')  # , 'Continue')

# Initial sleeping time (in seconds) in order to launch a scheduled protocol.
# This value is multiply to the protocol level into the workflow.
INITIAL_SLEEP_TIME = 30

# Maximum time (in seconds) waiting for a scheduled protocol to check if it
# can be launched.
MAX_SLEEP_TIME = 120


# Steps execution mode
STEPS_SERIAL = 0      # Execute steps serially, some of the steps can be mpi programs
STEPS_PARALLEL = 1    # Execute steps in parallel through threads

# Level of expertise for the input parameters, mainly used in the protocol form
LEVEL_NORMAL = 0
LEVEL_ADVANCED = 1
LEVEL_CHOICES = ('Normal', 'Advanced')

# Param names for GPU processing
USE_GPU = 'useGpu'
GPU_LIST = 'gpuList'
VOID_GPU = 99

# Job management
UNKNOWN_JOBID = -1

# File sizes
SIZE_1KB = 1024
SIZE_1MB = SIZE_1KB * SIZE_1KB
SIZE_1GB = SIZE_1MB * SIZE_1KB
SIZE_1TB = SIZE_1GB * SIZE_1KB