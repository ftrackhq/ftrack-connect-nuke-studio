# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import FnAssetAPI.logging
import ftrack


class DefaultResolution(object):
    '''Return default value for resolution setting when exporting project.'''

    def launch(self, event):
        '''Return default setting.'''

        FnAssetAPI.logging.debug(
            'Loading default resolution setting from hook:\n{0}'.format(
                event['data']['available_settings']
            )
        )

        if '1920x1080 HD_1080' in event['data']['available_settings']:
            return '1920x1080 HD_1080'

        return event['data']['available_settings'][0]

    def register(self):
        '''Register hook.'''
        ftrack.EVENT_HUB.subscribe(
            'topic=ftrack.connect.nuke-studio.get-default-resolution',
            self.launch
        )


def register(registry, **kw):
    '''Register hooks for default resolution setting.'''
    plugin = DefaultResolution()
    plugin.register()
