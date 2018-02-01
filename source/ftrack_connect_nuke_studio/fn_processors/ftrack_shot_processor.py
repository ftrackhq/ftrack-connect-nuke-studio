# Copyright (c) 2011 The Foundry Visionmongers Ltd.  All Rights Reserved.
import tempfile
import types
import os
import hiero
import time
import hiero.core
import hiero.ui
from hiero import core


from hiero.exporters.FnShotProcessor import ShotProcessor
from hiero.exporters.FnShotProcessor import buildTagsData, findTrackItemExportTag, getShotNameIndex
from hiero.exporters.FnEffectHelpers import ensureEffectsNodesCreated
from hiero.exporters.FnShotProcessorUI import ShotProcessorUI

from hiero.ui.FnTagFilterWidget import TagFilterWidget
from hiero.core.FnProcessor import _expandTaskGroup

from QtExt import QtCore, QtWidgets
from ftrack_connect_nuke_studio.ui.create_project import ProjectTreeDialog
from .ftrack_base import FtrackBase


class FtrackShotProcessor(ShotProcessor, FtrackBase):

    def __init__(self, preset, submission, synchronous=False):
        ShotProcessor.__init__(self, preset, submission, synchronous=synchronous)
        FtrackBase.__init__(self)


class FtrackShotProcessorUI(ShotProcessorUI, FtrackBase):

    def __init__(self, preset):
        FtrackBase.__init__(self)
        ShotProcessorUI.__init__(
            self,
            preset,
        )

    def updatePathPreview(self):
        self._pathPreviewWidget.setText('Ftrack Server: {0}'.format(self.session.server_url))

    def displayName(self):
        return "Ftrack"

    def toolTip(self):
        return "Process as Shots generates output on a per shot basis."
            
    def _checkExistingVersions(self, exportItems):
        """ Iterate over all the track items which are set to be exported, and check if they have previously
        been exported with the same version as the setting in the current preset.  If yes, show a message box
        asking the user if they would like to increment the version, or overwrite it. """

        for item in exportItems:
            self.logger.info('_checkExistingVersions of:{0}'.format(item.name()))

        return ShotProcessorUI._checkExistingVersions(
            self,
            exportItems,
        )

    def onItemSelected(self, item):
        self.logger.info(item.track)
    
    # def createPathPreviewWidget(self):
    #     # here we can manipulate the path preview