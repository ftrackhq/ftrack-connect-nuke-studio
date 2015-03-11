# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

import functools

import FnAssetAPI
from FnAssetAPI.ui.toolkit import QtGui
from ftrack_connect_nuke.ui import delegate
from ftrack_connect_nuke_studio.ui.create_project import ProjectTreeDialog



def openCreateProjectUI(*args, **kwargs):
    ''' Function to be triggered from createProject custom menu.
    '''
    import hiero
    parent = hiero.ui.mainWindow()
    ftags = []
    trackItems = args[0]
    for item in trackItems:
        tags = item.tags()
        tags = [tag for tag in tags if tag.metadata().hasKey('ftrack.type')]
        ftags.append((item, tags))

    dialog = ProjectTreeDialog(data=ftags, parent=parent)
    dialog.exec_()


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
