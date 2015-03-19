import nuke.assetmgr


class CustomBuild(
    nuke.assetmgr.nukestudiohost.hostAdaptor.NukeStudioHostAdaptor.ui.buildAssetTrackActions.BuildAssetTrackAction
):
    '''Build a track of items without using a ui.'''

    def __init__(self, sequence, *args, **kwargs):
        super(CustomBuild, self).__init__(*args, **kwargs)
        self._sequence = sequence

    def doit(self):
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
