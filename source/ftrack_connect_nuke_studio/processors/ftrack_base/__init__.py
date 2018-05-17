# :coding: utf-8
# :copyright: Copyright (c) 2018 ftrack

import os
import hiero
import logging
import ftrack_api
import time


FTRACK_PATH = os.path.join(
    '{ftrack_project_structure}',
    '{ftrack_asset}',
    '{ftrack_component}'
)



class FtrackProcessorError(Exception):
    pass


class FtrackProcessorValidationError(FtrackProcessorError):
    pass


class FtrackBase(object):
    '''
    wrap ftrack functionalities and methods
    '''

    ingored_locations = [
        'ftrack.server',
        'ftrack.review',
        'ftrack.origin',
        'ftrack.unmanaged',
        'ftrack.connect'
    ]

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )
        self.logger.setLevel(logging.DEBUG)
        self.session = ftrack_api.Session(auto_connect_event_hub=False)

    def timeStampString(self, localtime):
        return time.strftime('%Y/%m/%d %X', localtime)

    @property
    def hiero_version_touple(self):
        return (
            hiero.core.env['VersionMajor'],
            hiero.core.env['VersionMinor'],
            hiero.core.env['VersionRelease'].split('v')[-1]
        )

    @property
    def ftrack_location(self):
        result = self.session.pick_location()
        # self.logger.info('location: %s' % result)
        return result

    @property
    def ftrack_origin_location(self):
        return self.session.query(
            'Location where name is "ftrack.origin"'
        ).one()

    @property
    def ftrack_server_location(self):
        return self.session.query(
            'Location where name is "ftrack.server"'
        ).one()


class FtrackBasePreset(FtrackBase):
    def __init__(self, name, properties, **kwargs):
        super(FtrackBasePreset, self).__init__(name, properties)

        current_location = self.ftrack_location
        if current_location['name'] in self.ingored_locations:
            raise FtrackProcessorError(
                '{0} is an invalid location. Please setup'
                ' a centralised storage scenario or custom location.'.format(
                    current_location['name']
                )
            )

        self.set_export_root()
        self.set_ftrack_properties(properties)

    def set_ftrack_properties(self, properties):
        properties = self.properties()
        properties.setdefault('ftrack', {})

        # add placeholders for default task properties
        self.properties()['ftrack']['component_name'] = None
        self.properties()['ftrack']['component_pattern'] = None
        self.properties()['ftrack']['task_type'] = 'Generic'

        # add placeholders for default processor
        self.properties()['ftrack']['project_schema'] = 'Film Pipeline'
        self.properties()['ftrack']['processor_id'] = hash(self.__class__.__name__)

        # options
        self.properties()['ftrack']['opt_publish_thumbnail'] = True
        self.properties()['ftrack']['opt_publish_review'] = False

    def set_export_root(self):
        self.properties()['exportRoot'] = self.ftrack_location.accessor.prefix

    def resolve_ftrack_project_structure(self, task):
        trackItem = task._item

        project_name = task.projectName()

        if not isinstance(trackItem, hiero.core.Sequence):
            sequence_name = trackItem.name().split('_')[0]
            shot_name = trackItem.name().split('_')[1]
        else:
            sequence_name = trackItem.name()
            shot_name = ''

        task_name = self.properties()['ftrack']['task_type']

        return os.path.sep.join([
            project_name,
            sequence_name,
            shot_name,
            task_name
        ])

    def resolve_ftrack_asset(self, task):
        return task._preset.name()

    def resolve_ftrack_component(self, task):
        component_name = self.properties()['ftrack']['component_name']
        extension = self.properties()['ftrack']['component_pattern']
        component_full_name = '{0}{1}'.format(component_name, extension)
        return component_full_name

    def addFtrackResolveEntries(self, resolver):

        resolver.addResolver(
            '{ftrack_project_structure}',
            'Ftrack project structure.',
            lambda keyword, task: self.resolve_ftrack_project_structure(task)
        )

        resolver.addResolver(
            '{ftrack_asset}',
            'Ftrack asset name.',
            lambda keyword, task: self.resolve_ftrack_asset(task)
        )

        resolver.addResolver(
            '{ftrack_component}',
            'Ftrack component name.',
            lambda keyword, task: self.resolve_ftrack_component(task)
        )

