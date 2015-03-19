# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

import functools

import FnAssetAPI
from FnAssetAPI.ui.toolkit import QtGui
from ftrack_connect_foundry.ui import delegate
from ftrack_connect_nuke_studio.ui.create_project import ProjectTreeDialog
import ftrack_connect_nuke_studio.build_track


def openCreateProjectUI(*args, **kwargs):
    ''' Function to be triggered from createProject custom menu.
    '''
    import hiero
    parent = hiero.ui.mainWindow()
    ftags = []
    trackItems = args[0]
    for item in trackItems:
        if not isinstance(item,  hiero.core.TrackItem):
            continue
        tags = item.tags()
        tags = [tag for tag in tags if tag.metadata().hasKey('ftrack.type')]
        ftags.append((item, tags))

    dialog = ProjectTreeDialog(data=ftags, parent=parent)
    dialog.exec_()


def buildComps(data):
    '''Build comps from *data*.'''
    if not data:
        return

    sequence = data[0].sequence()

    buildComp = ftrack_connect_nuke_studio.build_track.CustomBuild(sequence)
    buildComp.setTrackItems(data)
    buildComp.setOptions({
        'trackName': 'foo',
        'criteriaString': 'latest,ftrack://44dd23b6-4164-11df-9218-0019bb4983d8?entityType=tasktype,True',
        'shotParentEntity': None,
        'interactive': False,
        'ignoreClips': False
    })
    buildComp.doit()


class Delegate(delegate.Delegate):
    def __init__(self, bridge):
        super(Delegate, self).__init__(bridge)

    def populateUI(self, uiElement, specification, context):
        super(Delegate, self).populateUI(uiElement, specification, context)

        host = FnAssetAPI.SessionManager.currentSession().getHost()
        if host and host.getIdentifier() == 'uk.co.foundry.nukestudio': 
            import nuke.assetmgr
            if context.locale.isOfType(nuke.assetmgr.nukestudiohost.hostAdaptor.NukeStudioHostAdaptor.specifications.HieroTimelineContextMenuLocale):                
                data = context.locale.getData().get('event').sender.selection()
                cmd = functools.partial(openCreateProjectUI, data)
                action = QtGui.QAction(QtGui.QPixmap(':icon-ftrack-box'), 'Create Project', uiElement)
                action.triggered.connect(cmd)
                uiElement.addAction( action )

                buildCompsCommand = functools.partial(buildComps, data)
                buildCompsAction = QtGui.QAction(
                    QtGui.QPixmap(':icon-ftrack-box'), 'Build assetised comps',
                    uiElement
                )
                buildCompsAction.triggered.connect(buildCompsCommand)
                uiElement.addAction(buildCompsAction)
