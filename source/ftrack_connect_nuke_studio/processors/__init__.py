# :coding: utf-8
# :copyright: Copyright (c) 2018 ftrack

import logging

import hiero

from ftrack_connect_nuke_studio.processors.ftrack_base.ftrack_shot_processor import (
    FtrackShotProcessor,
    FtrackShotProcessorPreset,
    FtrackShotProcessorUI
)
from ftrack_connect_nuke_studio.processors.ftrack_base.ftrack_timeline_processor import FtrackTimelineProcessorPreset
from ftrack_connect_nuke_studio.processors.ftrack_tasks.ftrack_nuke_shot_exporter import FtrackNukeShotExporterPreset
from ftrack_connect_nuke_studio.processors.ftrack_tasks.ftrack_nuke_render_exporter import FtrackNukeRenderExporterPreset
from ftrack_connect_nuke_studio.processors.ftrack_tasks.ftrack_audio_exporter import FtrackAudioExporterPreset
from ftrack_connect_nuke_studio.processors.ftrack_tasks.ftrack_edl_exporter import FtrackEDLExporterPreset
from ftrack_base import FTRACK_PATH

registry = hiero.core.taskRegistry

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

#override foundry logger to get some useful output
hiero.core.log = logger


def register_processors():

    # Register the base preset for ftrack shot processor.
    # this could be moved to a discover function
    shot_name = 'Ftrack Shot Preset'

    nuke_script_processor = FtrackNukeShotExporterPreset(
        'NukeScript',
        {
            'readPaths': [],
            'writePaths': [FTRACK_PATH],
            'timelineWriteNode': '',
        }
    )

    nuke_render_processor = FtrackNukeRenderExporterPreset(
        'Plate',
        {
            'file_type': 'dpx',
            'dpx': {
                'datatype': '10 bit'
            }
        }
    )

    audio_processor = FtrackAudioExporterPreset(
        'Audio', {}
    )

    shot_properties = {
        'exportTemplate': (
            (FTRACK_PATH, nuke_script_processor),
            (FTRACK_PATH, nuke_render_processor),
            # (ftrack_shot_path, audio_processor),

        ),
        'cutLength': True,
    }

    shot_preset = FtrackShotProcessorPreset(
        shot_name,
        shot_properties
    )

    # Register the base preset for ftrack timeline processor.
    # this could be moved to a discover function
    timeline_name = 'Ftrack Timeline Preset'

    edl_processor = FtrackEDLExporterPreset(
        'EDL', {}
    )

    timeline_properties = {
        'exportTemplate': (
            (FTRACK_PATH, edl_processor),
        ),
        'cutLength': True,
    }

    timeline_preset = FtrackTimelineProcessorPreset(
        timeline_name,
        timeline_properties

    )

    registers = [
        (shot_name, shot_preset),
        (timeline_name, timeline_preset),

    ]

    for register_name, register_preset in registers:
        existing = [p.name() for p in registry.localPresets()]
        if shot_name in existing:
            registry.removeProcessorPreset(register_name)
        logger.debug('Registering Ftrack Processor: {0}'.format(register_name))
        hiero.core.taskRegistry.removeProcessorPreset(register_name)
        hiero.core.taskRegistry.addProcessorPreset(register_name, register_preset)
