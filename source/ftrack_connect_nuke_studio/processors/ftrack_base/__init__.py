# :coding: utf-8
# :copyright: Copyright (c) 2018 ftrack

import logging
import hiero
import datetime
from ftrack_connect_nuke_studio.base import FtrackBase
from ftrack_connect_nuke_studio.template import match, get_project_template
import ftrack_connect_nuke_studio.exception


logger = logging.getLogger(__name__)


FTRACK_PROJECT_STRUCTURE = FtrackBase.path_separator.join([
    '{ftrack_project_structure}',
    '{ftrack_version}',
    '{ftrack_component}'
])


class FtrackProcessorError(Exception):
    ''' Base ftrack processor error. '''


class FtrackProcessorValidationError(FtrackProcessorError):
    ''' Ftrack processor validation error. '''


def remove_reference_ftrack_project(project):
    '''Remove reference ftrack tag from *project*.'''
    for sequence in project.sequences():
        for tag in sequence.tags()[:]:
            if tag.name() == 'ftrack.project_reference':
                logger.debug('removing project reference')
                sequence.removeTag(tag)


def lock_reference_ftrack_project(project):
    '''Set *project* reference tag to locked so cannot be updated.'''
    for sequence in project.sequences():
        for tag in sequence.tags():
            if tag.name() == 'ftrack.project_reference':
                logger.debug('Locking project')
                tag.metadata().setValue('ftrack.project_reference.locked', str(1))


def get_reference_ftrack_project(project):
    '''Return ftrack project reference stored on *project* and whether is locked.'''
    ftrack_project_id = None
    is_project_locked = False
    # Fetch the templates from tags on sequences on the project.
    # This is a workaround due to that projects do not have tags or metadata.
    for sequence in project.sequences():
        for tag in sequence.tags():
            if tag.name() == 'ftrack.project_reference':
                ftrack_project_id = tag.metadata().value('ftrack.project_reference.id')
                is_project_locked = bool(int(tag.metadata().value('ftrack.project_reference.locked')))
                break

        if ftrack_project_id:
            break

    return ftrack_project_id, is_project_locked


def set_reference_ftrack_project(project, project_id):
    '''Set *project* tags to ftrack *project_id* if doesn't exist.'''
    for sequence in project.sequences():
        existing_tag = None
        for tag in sequence.tags():
            if tag.name() == 'ftrack.project_reference':
                existing_tag = tag
                break

        if existing_tag and bool(int(existing_tag.metadata().value('ftrack.project_reference.locked'))):
            # project is locked , not much we can do ...
            logger.debug('Tag {} is locked....'.format(tag))
            continue

        if existing_tag:
            # tag exists and is not locked, we can update...
            existing_tag.metadata().setValue('ftrack.project_reference.id', project_id)
            # tag.setVisible(False)
        else:
            # tag does not exists
            tag = hiero.core.Tag('ftrack.project_reference')
            tag.metadata().setValue('ftrack.project_reference.id', project_id)
            tag.metadata().setValue('ftrack.project_reference.locked', str(0))
            sequence.addTag(tag)


class FtrackBasePreset(FtrackBase):

    def __init__(self, name, properties, **kwargs):
        ''' Initialise class with *name* and *properties*, '''
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
        self._timeStamp = datetime.datetime.now()

        if not properties.get('ftrack'):
            self.set_ftrack_properties(properties)

    def timeStamp(self):
        '''timeStamp(self)
        Returns the datetime object from time of task creation'''
        return self._timeStamp

    def set_ftrack_properties(self, properties):
        ''' Ensure and extend common ftrack *properties* . '''
        properties = self.properties()
        properties.setdefault('ftrack', {})

        self.properties()['ftrack']['opt_publish_metadata'] = True
        self.properties()['ftrack']['opt_publish_reviewable'] = True
        self.properties()['ftrack']['opt_publish_thumbnail'] = False
        self.properties()['useAssets'] = False
        self.properties()['keepNukeScript'] = True

    def set_export_root(self):
        '''Set project export root to current ftrack location's accessor prefix.'''
        self.properties()['exportRoot'] = self.ftrack_location.accessor.prefix

    def resolve_ftrack_project_structure(self, task):
        ''' Return context for the given *task*.

        data returned from this resolver are expressed as:
        <object_type>:<object_name>|<object_type>:<object_name>|....
        '''

        ''' Return project name for the given *task*. '''
        project = task._project
        ftrack_project_id , project_is_locked = get_reference_ftrack_project(project)
        ftrack_project = self.session.get('Project', ftrack_project_id)
        ftrack_project_name = ftrack_project['full_name']

        track_item = task._item
        template = get_project_template(task._project)

        # Inject project as first item.
        data = ['Project:{}'.format(ftrack_project_name)]

        if not isinstance(track_item, hiero.core.Sequence):
            try:
                results = match(track_item, template)
            except ftrack_connect_nuke_studio.exception.TemplateError:
                # we can happly return None as if the validation does not goes ahead
                # the shot won't be created.
                return None

            for result in results:
                sanitised_result = self.sanitise_for_filesystem(result['name'])
                composed_result = '{}:{}'.format(result['object_type'], sanitised_result)
                data.append(composed_result)

        result_data = '|'.join(data)
        return result_data

    def resolve_ftrack_version(self, task):
        ''' Return version for the given *task*.'''
        version = 1  # first version is 1

        if not self._components:
            return 'v{:03d}'.format(version)

        has_data = self._components.get(
            task._item.parent().name(), {}
        ).get(
            task._item.name(), {}
        ).get(task.component_name())

        if not has_data:
            return 'v{:03d}'.format(version)

        version = str(has_data['component']['version']['version'])
        return 'v{:03d}'.format(version)

    def resolve_ftrack_component(self, task):
        ''' Return component for the given *task*.'''
        component_name = self.sanitise_for_filesystem(task._preset.name())
        extension = self.properties()['ftrack']['component_pattern']
        component_full_name = '{0}{1}'.format(component_name, extension)
        return component_full_name.lower()

    def addFtrackResolveEntries(self, resolver):
        ''' Add custom ftrack resolver in *resolver*. '''

        resolver.addResolver(
            '{ftrack_project_structure}',
            'Ftrack context contains Project, Episodes, Sequence and Shots.',
            lambda keyword, task: self.resolve_ftrack_project_structure(task)
        )

        resolver.addResolver(
            '{ftrack_version}',
            'Ftrack version contains Task, Asset and AssetVersion.',
            lambda keyword, task: self.resolve_ftrack_version(task)
        )

        resolver.addResolver(
            '{ftrack_component}',
            'Ftrack component name in AssetVersion.',
            lambda keyword, task: self.resolve_ftrack_component(task)
        )

        # Provide common resolver from ShotProcessorPreset
        resolver.addResolver(
            "{clip}",
            "Name of the clip used in the shot being processed",
            lambda keyword, task: task.clipName()
        )

        resolver.addResolver(
            "{shot}",
            "Name of the shot being processed",
            lambda keyword, task: task.shotName()
        )

        resolver.addResolver(
            "{track}",
            "Name of the track being processed",
            lambda keyword, task: task.trackName()
        )

        resolver.addResolver(
            "{sequence}",
            "Name of the sequence being processed",
            lambda keyword, task: task.sequenceName()
        )


