import hiero.core
from hiero.exporters.FnAudioExportTask import AudioExportTask, AudioExportPreset
from hiero.exporters.FnAudioExportUI import AudioExportUI

from ftrack_base import FtrackBasePreset, FtrackBase, FtrackBaseProcessor


class FtrackAudioExporter(AudioExportTask, FtrackBaseProcessor):

    def __init__(self, initDict):
        AudioExportTask.__init__(self, initDict)
        FtrackBaseProcessor.__init__(self, initDict)
        self._do_publish = self._item.mediaType() is hiero.core.TrackItem.MediaType.kVideo

    def updateItem(self, originalItem, localtime):
        FtrackBaseProcessor.updateItem(self, originalItem, localtime)
        self.logger.info(self.resolvedExportPath())

    def finishTask(self):
        FtrackBaseProcessor.finishTask(self)
        AudioExportTask.finishTask(self)

    def _makePath(self):
        # disable making file paths
        FtrackBaseProcessor._makePath(self)


class FtrackAudioExporterPreset(AudioExportPreset, FtrackBasePreset):

    def __init__(self, name, properties):
        AudioExportPreset.__init__(self, name, properties)
        FtrackBasePreset.__init__(self, name, properties)
        self._parentType = FtrackAudioExporter

        # Update preset with loaded data
        self.properties().update(properties)

    def set_ftrack_properties(self, properties):
        FtrackBasePreset.set_ftrack_properties(self, properties)
        properties = self.properties()
        properties.setdefault('ftrack', {})

        # add placeholders for default ftrack defaults
        self.properties()['ftrack']['task_type'] = 'Editing'
        self.properties()['ftrack']['asset_type_code'] = 'audio'
        self.properties()['ftrack']['component_name'] = 'main'
        self.properties()['ftrack']['component_pattern'] = '.{ext}'

    def addCustomResolveEntries(self, resolver):
        FtrackBasePreset.addFtrackResolveEntries(self, resolver)
        # ensure to have {ext} set to a wav fixed extension
        resolver.addResolver("{ext}", "Extension of the file to be output", 'wav')


class FtrackAudioExporterUI(AudioExportUI, FtrackBase):
    def __init__(self, preset):
        AudioExportUI.__init__(self, preset)
        FtrackBase.__init__(self, preset)

        self._displayName = "Ftrack Audio Exporter"
        self._taskType = FtrackAudioExporter


hiero.core.taskRegistry.registerTask(FtrackAudioExporterPreset, FtrackAudioExporter)
hiero.ui.taskUIRegistry.registerTaskUI(FtrackAudioExporterPreset, FtrackAudioExporterUI)