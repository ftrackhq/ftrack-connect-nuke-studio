# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import nuke.assetmgr
import FnAssetAPI

import ftrack

class CustomBuild(
    nuke.assetmgr.nukestudiohost.hostAdaptor.NukeStudioHostAdaptor.ui.buildAssetTrackActions.BuildAssetTrackAction
):
    '''Build a track of items without using a ui.'''

    def __init__(self, sequence, *args, **kwargs):
        '''Instansiate custom build action with *sequence*.'''
        super(CustomBuild, self).__init__(*args, **kwargs)
        self._sequence = sequence

    def doit(self):
        '''Build track.'''
        selection = self.getTrackItems()

        sequence = self._sequence
        project = sequence.project()

        if not self.configure(project, selection):
            return

        self._buildTrack(selection, sequence, project)

        if self._errors:
            msgBox = PySide.QtGui.QMessageBox(hiero.ui.mainWindow())
            msgBox.setWindowTitle("Build Media Track")
            msgBox.setText("There were problems building the track.")
            msgBox.setDetailedText( '\n'.join(self._errors) )
            msgBox.exec_()
            self._errors = []


def build_compositing_script_track(
    track_items, task_type=None, track_name='Comps'
):
    '''Build track with scripts from *track_items*.'''
    FnAssetAPI.logging.debug(
        'Build track of scripts from {0}'.format(track_items)
    )
    if not track_items:
        return

    if task_type is None:
        task_type = ftrack.TaskType('Compositing')

    # Criteria string is formatted like:
    # latest|approved,task type entity ref,prefer-nuke-script
    criteria = 'latest,{0},True'.format(task_type.getEntityRef())
    sequence = track_items[0].sequence()

    action = CustomBuild(sequence)
    action.setTrackItems(track_items)
    action.setOptions({
        'trackName': track_name,
        'criteriaString': criteria,
        'shotParentEntity': None,
        'interactive': False,
        'ignoreClips': False
    })
    action.doit()
