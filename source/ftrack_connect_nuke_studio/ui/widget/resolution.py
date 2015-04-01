# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import hiero
import ftrack_legacy as ftrack


class Resolution(hiero.ui.FormatChooser):
    '''Wrap hiero widget for promoted qtDesigner one.'''

    def __init__(self, *args, **kwargs):
        super(Resolution, self).__init__(*args, **kwargs)

        result = ftrack.EVENT_HUB.publish(
            ftrack.Event(
                topic='ftrack.connect.nuke-studio.get-default-resolution',
                data=dict(
                    available_settings=[
                        self.itemText(index) for index in range(self.count())
                    ]
                )
            ),
            synchronous=True
        )

        if result:

            # Try to find the result and if found set the index as current
            # index.
            index = self.findText(result[0])

            if index:
                self.setCurrentIndex(index)
