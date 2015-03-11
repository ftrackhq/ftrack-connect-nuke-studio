# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack
import FnAssetAPI
from ftrack_connect_nuke import manager

class ManagerInterface(manager.ManagerInterface):
    def initialize(self):
        '''Prepare for interaction with the current host.'''
        super(ManagerInterface, self).initialize()

        host = FnAssetAPI.SessionManager.currentSession().getHost()
        if host and host.getIdentifier() == 'uk.co.foundry.nukestudio':

            from hiero.core import events
            from ftrack_connect_nuke_studio.ui.tag_manager import TagManager
            from ftrack_connect_nuke_studio.ui.tag_drop_handler import TagDropHandler

            self.tag_handler = TagDropHandler()

            # after the project load , create the ftrack tags.
            events.registerInterest(
                'kStartup',
                TagManager
            )


