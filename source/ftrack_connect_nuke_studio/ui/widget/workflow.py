# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

from PySide import QtGui

import ftrack


class Workflow(QtGui.QComboBox):
    '''Expose availble workflows from ftrack's server.'''
    def __init__(self, parent=None):
        super(Workflow, self).__init__(parent=parent)
        self._schema = ftrack.getProjectSchemes()
        for schemata in self._schema:
            self.addItem(schemata.get('name'))
