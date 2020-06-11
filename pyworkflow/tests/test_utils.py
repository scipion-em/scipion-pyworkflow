#!/usr/bin/env python
# coding: latin-1
"""
Created on Mar 25, 2014

@author: airen
@author: roberto.marabini
"""
def wait(condition, timeout=30):
    """ Wait until "condition" returns False or return after timeout (seconds)
    param"""
    t0 = time.time()

    while condition():
        time.sleep(1)

        # Check timeout
        tDelta = time.time()

        if tDelta - t0 >= timeout:
            print("Wait timed out after ", timeout, " seconds")
            return
