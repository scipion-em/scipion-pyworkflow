""" Module to define pyworkflow exceptions"""
from pyworkflow import DOCSITEURLS


class PyworkflowException(Exception):
    """Root exception it has an extra attribute url that is meant to provide
     information about the error and how to solve it"""
    def __init__(self, *args, url=DOCSITEURLS.CONTACTUS):
        self._url = url
        super().__init__(*args)

    def getUrl(self):
        return self._url
    @classmethod
    def raiseFromException(cls, e, message, url=DOCSITEURLS.CONTACTUS):
        """ Creates a Pyworkflow exception from an existing exception"""
        message = "%s \n Original error message: %s" % (message, str(e))

        raise PyworkflowException(message, url) from None

class ValidationException(PyworkflowException):
    """ Validation exception"""
    pass

class PersistenceException(PyworkflowException):
    """ Exceptions related to persistence"""
