# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es)
# *              Jose Gutierrez (jose.gutierrez@cnb.csic.es)
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
This module is mainly for the Viewer class, which 
serve as base for implementing visualization tools(Viewer sub-classes).
"""

DESKTOP_TKINTER = 'tkinter'
WEB_DJANGO = 'django'


class Wizard(object):
    """ This is a special case of GUI to help the user selecting important parameters.

    The _targets attribute is used to define to which parameters the Wizard can deal with.
    It will be a list of tuples such as::

        _targets = [(DefImportMicrographs, ['voltage', sphericalAberration']), (DefCTFMicrographs, ['lowRes', 'highRes'])]

    """

    _targets = []
    _environments = [DESKTOP_TKINTER] # This can be ignored

    def show(self, form, *params):
        """
        EMPTY METHOD. Needs to be implemented in your class. This will be called to show the wizard.

        :param form: the protocol form, given access to to all parameters. Some times the same wizard will modify several elements in the form.
        :param params: a list of params to modify. Sometimes the wizard can be generic and can be used for different parameters in the same form.
        """
        pass
    
    def getView(self):
        """
        EMPTY METHOD. Deprecated.This method should return the string value of the view in web
        that will respond to this wizard. This method only should be implemented
        in those wizards that have WEB_DJANGO environment defined. 
        """
        return None
