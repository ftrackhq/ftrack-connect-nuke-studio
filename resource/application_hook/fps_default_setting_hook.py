# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import FnAssetAPI.logging
import ftrack


class DefaultFps(object):
    '''Return default value for fps setting when exporting project.'''

    def launch(self, event):
        '''Return default setting.'''

        FnAssetAPI.logging.debug('Loading default fps setting from hook.')

        if '25' in event['data']['available_settings']:
            return '25'

        return event['data']['available_settings'][0]

    def register(self):
        '''Register hook.'''
        ftrack.EVENT_HUB.subscribe(
            'topic=ftrack.connect.nuke-studio.get-default-fps',
            self.launch
        )


def register(registry, **kw):
    '''Register hooks for default fps setting.'''
    plugin = DefaultFps()
    plugin.register()
