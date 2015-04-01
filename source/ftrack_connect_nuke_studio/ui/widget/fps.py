# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import ftrack
import hiero
from FnAssetAPI.ui.toolkit import QtGui


class Fps(QtGui.QComboBox):
    '''Extract fps from hiero and expose them.'''
    def __init__(self, parent=None):
        super(Fps, self).__init__(parent=parent)

        available_fps = []
        for fps in hiero.core.defaultFrameRates():
            if fps.is_integer():
                safe_fps = str(int(fps))
            else:
                safe_fps = str(fps)

            self.addItem(safe_fps)
            available_fps.append(safe_fps)

        result = ftrack.EVENT_HUB.publish(
            ftrack.Event(
                topic='ftrack.connect.nuke-studio.get-default-fps',
                data=dict(
                    available_settings=available_fps
                )
            ),
            synchronous=True
        )

        if result:
            index = self.findText(result[0])
            self.setCurrentIndex(index)
