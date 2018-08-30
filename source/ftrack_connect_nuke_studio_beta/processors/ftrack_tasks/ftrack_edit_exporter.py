import hiero
from hiero.exporters.FnShotExporter import ShotTask
from hiero.core import TaskPresetBase
from hiero.ui import TaskUIBase

from ftrack_connect_nuke_studio_beta.processors.ftrack_base.ftrack_base_processor import (
    FtrackProcessorPreset,
    FtrackProcessor,
    FtrackProcessorUI
)


class FtrackEditExporter(ShotTask, FtrackProcessor):

    def __init__(self, initDict):
        '''Initialise task with *initDict*.'''
        ShotTask.__init__(self, initDict)
        FtrackProcessor.__init__(self, initDict)

    def _makePath(self):
        '''Disable file path creation.'''
        pass


class FtrackEditExporterPreset(TaskPresetBase, FtrackProcessorPreset):
    def __init__(self, name, properties, task=FtrackEditExporter):
        '''Initialise task with *name* and *properties*.'''
        TaskPresetBase.__init__(self, task, name)
        FtrackProcessorPreset.__init__(self, name, properties)
        # Update preset with loaded data
        self.properties().update(properties)
        self.setName('Edit')


class FtrackEditExporterUI(TaskUIBase, FtrackProcessorUI):
    def __init__(self, preset):
        """UI for NukeShotExporter task."""
        TaskUIBase.__init__(self, preset.parentType(), preset, "Ftrack Edit Publish")


hiero.core.taskRegistry.registerTask(FtrackEditExporterPreset, FtrackEditExporter)
hiero.ui.taskUIRegistry.registerTaskUI(FtrackEditExporterPreset, FtrackEditExporterUI)
