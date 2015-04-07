# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

import functools

import FnAssetAPI
import nuke
import ftrack_legacy as ftrack

from FnAssetAPI.ui.toolkit import QtGui
from ftrack_connect_foundry.ui import delegate

from nukescripts import panels

from ftrack_connect_nuke_studio.ui.create_project import ProjectTreeDialog
from ftrack_connect_nuke_studio.ui.crew import NukeCrew
from ftrack_connect_nuke_studio.ui.widget.info_view import (
    InfoView as _InfoView
)

from ftrack_connect_nuke_studio.build_track import (
    build_compositing_script_track
)


def publish_plates(track_items):
    ftrack.EVENT_HUB.publish(
        ftrack.Event(
            topic='ftrack.nukestudio.publish-plates',
            data={
                'track_items': track_items
            }
        ),
        synchronous=True
    )


def openCreateProjectUI(*args, **kwargs):
    ''' Function to be triggered from createProject custom menu.
    '''
    import hiero
    parent = hiero.ui.mainWindow()
    ftags = []
    trackItems = args[0]
    for item in trackItems:
        if not isinstance(item, hiero.core.TrackItem):
            continue
        tags = item.tags()
        tags = [tag for tag in tags if tag.metadata().hasKey('ftrack.type')]

        if tags:
            ftags.append((item, tags))

    dialog = ProjectTreeDialog(
        data=ftags, parent=parent, sequence=item.sequence()
    )
    dialog.exec_()


class Delegate(delegate.Delegate):
    def __init__(self, bridge):
        super(Delegate, self).__init__(bridge)

        # Add custom nuke studio widgets to the widget mapping.
        for widgetClass in (_InfoView,):
            identifier = widgetClass.getIdentifier()

            # Bind bridge as first argument to class on instantiation.
            boundWidgetClass = functools.partial(widgetClass, self._bridge)

            # The returned callable is expected to be a class with certain
            # class methods available. Therefore, also dynamically assign
            # original class methods to wrapper.
            for name in ('getIdentifier', 'getDisplayName', 'getAttributes'):
                setattr(boundWidgetClass, name, getattr(widgetClass, name))

            self._widgetMapping[identifier] = boundWidgetClass

    def populate_ftrack(self):
        '''Populate the ftrack menu with items.'''

        # Populate the ui
        nukeMenu = nuke.menu('Nuke')
        ftrackMenu = nukeMenu.addMenu('&ftrack')

        # Create the crew dialog entry in the menu
        panels.registerWidgetAsPanel(
            'ftrack_connect_nuke_studio.ui.crew.NukeCrew',
            'Crew',
            'widget.Crew'
        )
        ftrackMenu.addCommand(
            'Crew',
            'pane = nuke.getPaneFor("Properties.1");'
            'panel = nukescripts.restorePanel("widget.Crew");'
            'panel.addToPane(pane)'
        )

        ftrackMenu.addSeparator()

        ftrackMenu.addCommand(
            'Info',
            'pane = nuke.getPaneFor("Properties.1");'
            'panel = nukescripts.restorePanel("{identifier}");'
            'panel.addToPane(pane)'.format(
                identifier=_InfoView.getIdentifier()
            )
        )

    def populateUI(self, uiElement, specification, context):
        super(Delegate, self).populateUI(uiElement, specification, context)

        host = FnAssetAPI.SessionManager.currentSession().getHost()
        if host and host.getIdentifier() == 'uk.co.foundry.nukestudio':            
            try:
                from nuke.assetmgr.nukestudiohost.hostAdaptor import NukeStudioHostAdaptor as studioAdaptor
            except ImportError:
                from nuke.assetmgr.host.adaptor import StudioAdaptor as studioAdaptor

            if context.locale.isOfType(
                 studioAdaptor.specifications.HieroTimelineContextMenuLocale
            ):
                data = context.locale.getData().get('event').sender.selection()
                cmd = functools.partial(openCreateProjectUI, data)
                action = QtGui.QAction(
                    QtGui.QPixmap(':icon-ftrack-box'),
                    'Export project', uiElement
                )
                action.triggered.connect(cmd)
                uiElement.addAction(action)

                publishPlates = functools.partial(
                    publish_plates,
                    data
                )
                publishPlatesAction = QtGui.QAction(
                    QtGui.QPixmap(':icon-ftrack-box'), 'Publish plates',
                    uiElement
                )
                publishPlatesAction.triggered.connect(publishPlates)
                uiElement.addAction(publishPlatesAction)

                buildCompsCommand = functools.partial(
                    build_compositing_script_track,
                    data
                )
                buildCompsAction = QtGui.QAction(
                    QtGui.QPixmap(':icon-ftrack-box'), 'Build assetised comps',
                    uiElement
                )
                buildCompsAction.triggered.connect(buildCompsCommand)
                uiElement.addAction(buildCompsAction)

            self.populate_ftrack()
