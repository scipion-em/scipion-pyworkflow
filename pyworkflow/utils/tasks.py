# **************************************************************************
# *
# * Authors:     J.M. de la Rosa Trevin (delarosatrevin@scilifelab.se) [1]
# *
# * [1] SciLifeLab, Stockholm University
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
Utility functions to create threads running processing functions.
"""

from collections import OrderedDict
import threading


class TaskQueue:
    """ Queue of tasks where producers can deposit tasks and
    consumers can get it.
    """
    def __init__(self):
        self._done = 0
        self._condition = threading.Condition()
        self._tasks = []

    def getTask(self, proc):
        """ This function should be called from a consumer of this
        output instance.
        """
        self._condition.acquire()

        proc._print("Inside condition lock, queue._done: ", self._done)

        doWait = True
        task = None

        while doWait:
            doWait = False
            if self._tasks:
                proc._print("There are tasks")
                task = self._tasks.pop(0)
            elif self._done > 0:
                proc._print("No tasks, but not Done, waiting...")
                self._condition.wait()
                doWait = True
            else:
                proc._print("No tasks and done, should return None task.")

        self._condition.release()

        # Return the task, either None if nothing else should be
        # done, or a task to be processed
        return task

    def putTask(self, task):
        """ This function should be used by subclasses of Output
        that produces items that will be used by consumers.
        """
        self._condition.acquire()
        self._tasks.append(task)
        self._condition.notify()
        self._condition.release()

    def notifyGeneratorStarts(self):
        """ When this queue is associated to a generator, this method should be
        used. Each generator should notify later when it is done and when all
        are done, the queue will trigger the Done signal.
        """
        self._condition.acquire()
        self._done += 1
        self._condition.release()

    def notifyGeneratorEnds(self):
        """ This function should be used by subclasses of Output
        when the output generation is finished. After this getTask
        should return None
        """
        self._condition.acquire()
        self._done -= 1
        if self._done == 0:
            self._condition.notifyAll()
        self._condition.release()

    def isDone(self):
        self._condition.acquire()
        is_done = self._done
        self._condition.release()
        return is_done


class TaskGenerator(threading.Thread):
    def __init__(self, generator, outputQueue=None,
                 name='', debug=False):
        """
        Params:
            generator: generator of new tasks
            outputQueue: where new tasks will be put.
                If None, a new queue will be created
        """
        threading.Thread.__init__(self)
        self.id = None
        self.name = name
        self.debug = debug
        self._generator = generator

        if outputQueue is None:
            self.outputQueue = TaskQueue()
        else:
            self.outputQueue = outputQueue

    def run(self):
        self.outputQueue.notifyGeneratorStarts()
        self.id = threading.get_ident()

        for task in self._generator():
            self.outputQueue.putTask(task)

        self.outputQueue.notifyGeneratorEnds()

    def _print(self, *args):
        """ Function to debug printing Generator's name. """
        if self.debug:
            print(">>> %s: " % self.name, *args)


class TaskProcessor(TaskGenerator):
    def __init__(self, inputQueue, processor, outputQueue=None,
                 name='', debug=False):
        TaskGenerator.__init__(self, self._process, outputQueue, name, debug)
        self._processor = processor
        self._inputQueue = inputQueue


    def _process(self):
        self._print("Getting new task...")
        task = self._inputQueue.getTask(self)
        while task is not None:
            self._print("Got task: '%s'" % task)

            yield self._processor(task)  # yield new processed task
            self._print("Getting new task...")
            task = self._inputQueue.getTask(self)

        self._print("Got task: None")


class TaskEngine:
    """ Simple class to add generator and processors.
    It will handle all threads start and join.
    """
    def __init__(self, debug=False):
        self.debug = debug
        self._nodes = OrderedDict()

    def _addNode(self, nodeClass, *args, **kwargs):
        name = kwargs.get('name', 'node-%02d' % len(self._nodes))
        if name in self._nodes:
            raise Exception("Duplicated node name '%s'" % name)

        kwargs['name'] = name
        if 'debug' not in kwargs:
            kwargs['debug'] = self.debug
        n = nodeClass(*args, **kwargs)
        self._nodes[name] = n
        return n

    def addGenerator(self, *args, **kwargs):
        return self._addNode(TaskGenerator, *args, **kwargs)

    def addProcessor(self, *args, **kwargs):
        return self._addNode(TaskProcessor, *args, **kwargs)

    def start(self):
        for n in self._nodes.values():
            n.start()

    def join(self):
        for n in self._nodes.values():
            n.join()
