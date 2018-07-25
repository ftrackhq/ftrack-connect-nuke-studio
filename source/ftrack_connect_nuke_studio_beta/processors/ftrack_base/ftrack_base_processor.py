# :coding: utf-8
# :copyright: Copyright (c) 2018 ftrack

import os
import time
import tempfile
import logging
import foundry.ui

import hiero.core
from hiero.ui.FnTaskUIFormLayout import TaskUIFormLayout
from hiero.ui.FnUIProperty import UIPropertyFactory
from hiero.core.FnExporterBase import TaskCallbacks
from hiero.exporters.FnTimelineProcessor import TimelineProcessor
from hiero.exporters.FnShotProcessor import getShotNameIndex

from ftrack_connect_nuke_studio_beta.processors.ftrack_base import (
    FtrackBasePreset,
    FtrackBase,
    FtrackProcessorValidationError,
    FtrackProcessorError
)

from QtExt import QtCore, QtWidgets, QtGui


class FtrackSettingsValidator(QtWidgets.QDialog):

    def __init__(self, session, error_data, missing_assets_types):

        '''
        Return a validator widget for the given *error_data* and *missing_assets_types*.
        '''

        super(FtrackSettingsValidator, self).__init__()

        self.setWindowTitle('Validation error')
        self._session = session

        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

        ftrack_icon = QtGui.QIcon(':/ftrack/image/default/ftrackLogoColor')
        self.setWindowIcon(ftrack_icon)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        box = QtWidgets.QGroupBox('An error occured in the current schema configuration.')

        self.layout().addWidget(box)

        box_layout = QtWidgets.QVBoxLayout()
        box.setLayout(box_layout)

        form_layout = TaskUIFormLayout()
        box_layout.addLayout(form_layout)

        for processor, values in error_data.items():
            form_layout.addDivider('Wrong {0} presets'.format(processor.__class__.__name__))

            # TODO: attribute should be reversed .... as they are appearing in the wrong order
            for attribute, valid_values in values.items():
                valid_values.insert(0, '- select a value -')
                key, value, label = attribute, valid_values, ' '.join(attribute.split('_'))
                tooltip = 'Set {0} value'.format(attribute)

                uiProperty = UIPropertyFactory.create(
                    type(value),
                    key=key,
                    value=value,
                    dictionary=processor._preset.properties()['ftrack'],
                    label=label + ':',
                    tooltip=tooltip
                )
                form_layout.addRow(label + ':', uiProperty)

        if missing_assets_types:
            form_layout.addDivider('Missing asset types')

            for missing_asset in missing_assets_types:
                create_asset_button = QtWidgets.QPushButton(
                    missing_asset.capitalize()
                )
                create_asset_button.clicked.connect(self.create_missing_asset)
                form_layout.addRow('create asset: ', create_asset_button)

        buttons = QtWidgets.QDialogButtonBox()
        buttons.setOrientation(QtCore.Qt.Horizontal)
        buttons.addButton('Cancel', QtWidgets.QDialogButtonBox.RejectRole)
        buttons.addButton('Accept', QtWidgets.QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout().addWidget(buttons)

    def create_missing_asset(self):
        sender = self.sender()
        asset_type = sender.text()
        self._session.ensure(
            'AssetType',
            {
                'short': asset_type.lower(),
                'name': asset_type
            }
        )
        try:
            self._session.commit()
        except Exception as error:
            QtWidgets.QMessageBox().critical(self, 'ERROR', str(error))
            return

        sender.setDisabled(True)


class FtrackProcessorPreset(FtrackBasePreset):
    def __init__(self, name, properties):
        super(FtrackProcessorPreset, self).__init__(name, properties)

    def set_ftrack_properties(self, properties):
        super(FtrackProcessorPreset, self).set_ftrack_properties(properties)


class FtrackProcessor(FtrackBase):
    def __init__(self, initDict):
        super(FtrackProcessor, self).__init__(initDict)

        # Store a reference of the origial initialization data.
        self._init_dict = initDict

        # Store a reference of the ftrack properties for easier access.
        self.ftrack_properties = self._preset.properties()['ftrack']

        # Note we do resolve {ftrack_version} as part of the {ftrack_asset} function.
        self.fn_mapping = {
            '{ftrack_project}': self._create_project_fragment,
            '{ftrack_sequence}': self._create_sequence_fragment,
            '{ftrack_shot}': self._create_shot_fragment,
            '{ftrack_asset}': self._create_asset_fragment,
            '{ftrack_version}': self._create_version_fragment,
            '{ftrack_component}': self._create_component_fragment
        }
        # these events gets emitted during taskStart and taskFinish
        TaskCallbacks.addCallback(TaskCallbacks.onTaskStart, self.setupExportPaths)
        TaskCallbacks.addCallback(TaskCallbacks.onTaskFinish, self.publishResultComponent)
        # progress for project creation
        self._create_project_progress_widget = None
        self._validate_project_progress_widget = None

    @property
    def schema(self):
        # Return the current ftrack project schema
        project_schema_name = self.ftrack_properties['project_schema']
        project_schema = self.session.query(
            'ProjectSchema where name is "{0}"'.format(project_schema_name)
        ).one()
        return project_schema

    @property
    def task_type(self):
        # Return the ftrack object for the task type set.
        task_type_name = self.ftrack_properties['task_type']
        task_types = self.schema.get_types('Task')
        filtered_task_types = [task_type for task_type in task_types if task_type['name'] == task_type_name]
        if not filtered_task_types:
            raise FtrackProcessorValidationError(task_types)
        return filtered_task_types[0]

    @property
    def task_status(self):
        # Return the ftrack object for the task status.
        try:
            task_statuses = self.schema.get_statuses('Task', self.task_type['id'])
        except ValueError as error:
            raise FtrackProcessorError(error)

        filtered_task_status = [task_status for task_status in task_statuses if task_status['name']]
        # Return first status found.
        return filtered_task_status[0]

    @property
    def shot_status(self):
        # Return the ftrack object for the shot status.
        shot_statuses = self.schema.get_statuses('Shot')
        filtered_shot_status = [shot_status for shot_status in shot_statuses if shot_status['name']]
        # Return first status found.
        return filtered_shot_status[0]

    @property
    def asset_version_status(self):
        # Return the ftrack object for the asset version status.
        asset_statuses = self.schema.get_statuses('AssetVersion')
        filtered_asset_status = [asset_status for asset_status in asset_statuses if asset_status['name']]
        return filtered_asset_status[0]

    def asset_type_per_task(self, task):
        # Return the ftrack object available asset type.
        asset_type = task._preset.properties()['ftrack']['asset_type_code']
        try:
            result = self.session.query(
                'AssetType where short is "{0}"'.format(asset_type)
            ).one()
        except Exception as e:
            raise FtrackProcessorError(e)
        return result

    def _create_project_fragment(self, name, parent, task, version):
        self.logger.debug('Creating project fragment: {} {} {} {}'.format(name, parent, task, version))

        project = self.session.query(
            'Project where name is "{0}"'.format(name)
        ).first()
        if not project:
            project = self.session.create('Project', {
                'name': name,
                'full_name': name,
                'project_schema': self.schema
            })
        return project

    def _create_sequence_fragment(self, name, parent, task, version):
        self.logger.debug('Creating sequence fragment: {} {} {} {}'.format(name, parent, task, version))

        sequence = self.session.query(
            'Sequence where name is "{0}" and parent.id is "{1}"'.format(name, parent['id'])
        ).first()
        if not sequence:
            sequence = self.session.create('Sequence', {
                'name': name,
                'parent': parent
            })
        return sequence

    def _create_shot_fragment(self, name, parent, task,version):
        self.logger.debug('Creating shot fragment: {} {} {} {}'.format(name, parent, task, version))

        shot = self.session.query(
            'Shot where name is "{0}" and parent.id is "{1}"'.format(name, parent['id'])
        ).first()
        if not shot:
            shot = self.session.create('Shot', {
                'name': name,
                'parent': parent,
                'status': self.shot_status
            })
        return shot

    def _create_asset_fragment(self, name, parent, task, version):
        self.logger.debug('Creating asset fragment: {} {} {} {}'.format(name, parent, task, version))

        asset = self.session.query(
            'Asset where name is "{0}" and parent.id is "{1}"'.format(name, parent['id'])
        ).first()

        if not asset:
            asset = self.session.create('Asset', {
                'name': name,
                'parent':  parent,
                'type': self.asset_type_per_task(task)
            })

        return asset

    def _create_version_fragment(self, name, parent, task, version):
        self.logger.debug('Creating version fragment: {} {} {} {}'.format(name, parent, task, version))

        task_name = self.ftrack_properties['task_type']
        ftask = self.session.query(
            'Task where name is "{0}" and parent.id is "{1}"'.format(task_name, parent['parent']['id'])
        ).first()

        if not ftask:
            ftask = self.session.create('Task', {
                'name': task_name,
                'parent': parent['parent'],
                'status': self.task_status,
                'type': self.task_type
            })

        if not version:
            comment = 'Published with: {0} From Nuke Studio : {1}.{2}.{3}'.format(
                self.__class__.__name__, *self.hiero_version_touple
            )
            version = self.session.create('AssetVersion', {
                'asset': parent,
                'status': self.asset_version_status,
                'comment': comment,
                'task': ftask
            })

        return version

    def _create_component_fragment(self, name, parent, task, version):
        self.logger.debug('Creating component fragment: {} {} {} {}'.format(name, parent, task, version))

        component = parent.create_component('/', {
            'name': task._preset.name().lower()
        }, location=None)

        return component

    def _skip_fragment(self, name, parent, task, version):
        self.logger.warning('Skpping: {0}'.format(name))

    def _create_extra_tasks(self, task_type_names, component):
        '''Create extra tasks based on dropped ftrack tags'''

        parent = component['version']['asset']['parent']  # Get Shot from component
        task_types = self.schema.get_types('Task')

        for task_type_name in task_type_names:
            filtered_task_types = [task_type for task_type in task_types if task_type['name'] == task_type_name]
            if len(filtered_task_types) != 1:
                self.logger.debug(
                    'Skipping {0} as is not a valid task type for schema {1}'.format(
                        task_type_name, self.schema['name'])
                )
                continue

            task_status = self.schema.get_statuses('Task', filtered_task_types[0]['id'])

            ftask = self.session.query(
                'Task where name is "{0}" and parent.id is "{1}"'.format(task_type_name, parent['id'])
            ).first()

            if not ftask:
                self.session.create('Task', {
                    'name': task_type_name,
                    'parent': parent,
                    'status': task_status[0],
                    'type': filtered_task_types[0]
                })

        self.session.commit()

    def create_project_structure(self, exportItems):
        self._create_project_progress_widget = foundry.ui.ProgressTask('Creating structure in ftrack...')
        progress_index = 0

        # ensure to reset components before creating a new project.
        self._components = {}
        versions = {}

        # provide access to tags.
        numitems = len(self._exportTemplate.flatten()) * len(exportItems)
        for (exportPath, preset) in self._exportTemplate.flatten():
            for exportItem in exportItems:
                trackItem = exportItem.item()

                progress_index += 1
                self._create_project_progress_widget.setProgress(int(100.0 * (float(progress_index) / float(numitems))))

                # collect task tags per clip
                task_tags = set()

                if not hasattr(trackItem, 'tags'):
                    continue

                for tag in trackItem.tags():
                    meta = tag.metadata()
                    if meta.hasKey('type') and meta.value('type') == 'ftrack':
                        task_name = meta.value('ftrack.name')
                        task_tags.add(task_name)

                # Skip effects track items.
                if isinstance(trackItem, hiero.core.EffectTrackItem):
                    self.logger.debug('Skipping {0}'.format(trackItem))
                    continue

                shotNameIndex = getShotNameIndex(trackItem)
                if isinstance(self, TimelineProcessor):
                    trackItem = exportItem.item().sequence()
                    shotNameIndex= ''

                # create entry points on where to store ftrack component and path data.
                self._components.setdefault(trackItem.name(), {})
                self._components[trackItem.name()].setdefault(preset.name(), {})

                retime = self._preset.properties().get('includeRetimes', False)

                cutHandles = None
                startFrame = None

                if self._preset.properties()['startFrameSource'] == 'Custom':
                    startFrame = self._preset.properties()['startFrameIndex']

                # If we are exporting the shot using the cut length (rather than the (shared) clip length)
                if self._preset.properties().get('cutLength'):
                    # Either use the specified number of handles or zero
                    if self._preset.properties().get('cutUseHandles'):
                        cutHandles = int(self._preset.properties()['cutHandles'])
                    else:
                        cutHandles = 0

                # Build TaskData seed
                taskData = hiero.core.TaskData(
                    preset,
                    trackItem,
                    preset.properties()['exportRoot'],
                    exportPath,
                    'v0',
                   self._exportTemplate,
                   project=trackItem.project(),
                   cutHandles=cutHandles,
                   retime=retime,
                   startFrame=startFrame,
                   startFrameSource=self._preset.properties()['startFrameSource'],
                   resolver=self._preset.createResolver(),
                   submission=self._submission,
                   skipOffline=self.skipOffline(),
                   presetId=hiero.core.taskRegistry.addPresetToProjectExportHistory(trackItem.project(), self._preset),
                   shotNameIndex=shotNameIndex
                )

                task = hiero.core.taskRegistry.createTaskFromPreset(preset, taskData)

                file_name = '{0}{1}'.format(
                    preset.name().lower(),
                    preset.properties()['ftrack']['component_pattern']
                )
                resolved_file_name = task.resolvePath(file_name)

                path = task.resolvePath(exportPath)
                path_id = os.path.dirname(path)
                versions.setdefault(path_id, None)

                parent = None  # After the loop this will be containing the component object.
                for template, token in zip(exportPath.split(self.path_separator), path.split(self.path_separator)):
                    if not versions[path_id] and parent and parent.entity_type == 'AssetVersion':
                        versions[path_id] = parent

                    fragment_fn = self.fn_mapping.get(template, self._skip_fragment)
                    parent = fragment_fn(token, parent, task, versions[path_id])

                self.session.commit()
                self._create_extra_tasks(task_tags, parent)

                # Extract ftrack path from structure and accessors.
                ftrack_shot_path = self.ftrack_location.structure.get_resource_identifier(parent)

                # Ftrack sanitize output path, but we need to retain the original on here
                # otherwise foo.####.ext becomes foo.____.ext
                tokens = ftrack_shot_path.split(self.path_separator)

                tokens[-1] = resolved_file_name
                ftrack_shot_path = self.path_separator.join(tokens)

                ftrack_path = str(os.path.join(self.ftrack_location.accessor.prefix, ftrack_shot_path))

                data = {
                    'component': parent,
                    'path': ftrack_path,
                    'published': False
                }

                self._components[trackItem.name()][preset.name()] = data
                self.addFtrackTag(trackItem, task)

        self._create_project_progress_widget = None

    def addFtrackTag(self, originalItem, task):
        if not hasattr(originalItem, 'tags'):
            return

        item = task._item

        localtime = time.localtime(time.time())

        start, end = task.outputRange(clampToSource=False)
        start_handle, end_handle = task.outputHandles()

        task_id = str(task._preset.properties()['ftrack']['task_id'])

        data = self._components[originalItem.name()][task._preset.name()]
        component = data['component']

        path = data['path']
        frameoffset = start if start else 0

        collate = getattr(task,'_collate', False)
        applyingRetime = (task._retime and task._cutHandles is not None) or collate
        appliedRetimesStr = '1' if applyingRetime else '0'

        existingTag = None
        for tag in originalItem.tags():
            if tag.metadata().hasKey('tag.presetid') and tag.metadata()['tag.presetid'] == task_id:
                existingTag = tag
                break

        if existingTag:
            existingTag.metadata().setValue('tag.version_id', component['version']['id'])
            existingTag.metadata().setValue('tag.asset_id', component['version']['asset']['id'])
            existingTag.metadata().setValue('tag.version', str(component['version']['version']))
            existingTag.metadata().setValue('tag.path', path)
            existingTag.metadata().setValue('tag.pathtemplate', task._exportPath)

            existingTag.metadata().setValue('tag.startframe', str(start))
            existingTag.metadata().setValue('tag.duration', str(end - start+1))
            existingTag.metadata().setValue('tag.starthandle', str(start_handle))
            existingTag.metadata().setValue('tag.endhandle', str(end_handle))
            existingTag.metadata().setValue('tag.frameoffset', str(frameoffset))
            existingTag.metadata().setValue('tag.localtime', str(localtime))
            existingTag.metadata().setValue('tag.appliedretimes', appliedRetimesStr)

            if task._preset.properties().get('keepNukeScript'):
                existingTag.metadata().setValue('tag.script', task.resolvedExportPath())

            if task._cutHandles:
                existingTag.metadata().setValue('tag.handles', str(task._cutHandles))

            if isinstance(item, hiero.core.TrackItem):
                existingTag.metadata().setValue('tag.sourceretime', str(item.playbackSpeed()))

            originalItem.removeTag(existingTag)
            originalItem.addTag(existingTag)
            return

        tag = hiero.core.Tag(
            '{0}'.format(task._preset.name()),
            ':/ftrack/image/default/ftrackLogoColor',
            False
        )
        tag.metadata().setValue('tag.provider', 'ftrack')

        tag.metadata().setValue('tag.presetid', task_id)
        tag.metadata().setValue('tag.component_id', component['id'])
        tag.metadata().setValue('tag.version_id', component['version']['id'])
        tag.metadata().setValue('tag.asset_id', component['version']['asset']['id'])
        tag.metadata().setValue('tag.version', str(component['version']['version']))
        tag.metadata().setValue('tag.path', path)
        tag.metadata().setValue('tag.description', 'ftrack {0}'.format(task._preset.name()))

        tag.metadata().setValue('tag.pathtemplate', task._exportPath)

        tag.metadata().setValue('tag.startframe', str(start))
        tag.metadata().setValue('tag.duration', str(end - start+1))
        tag.metadata().setValue('tag.starthandle', str(start_handle))
        tag.metadata().setValue('tag.endhandle', str(end_handle))
        tag.metadata().setValue('tag.frameoffset', str(frameoffset))
        tag.metadata().setValue('tag.localtime', str(localtime))
        tag.metadata().setValue('tag.appliedretimes', appliedRetimesStr)

        if task._preset.properties().get('keepNukeScript'):
            tag.metadata().setValue('tag.script', task.resolvedExportPath())

        if task._cutHandles:
            tag.metadata().setValue('tag.handles', str(task._cutHandles))

        if isinstance(item, hiero.core.TrackItem):
            tag.metadata().setValue('tag.sourceretime', str(item.playbackSpeed()))

        originalItem.addTag(tag)

    def setupExportPaths(self, task):
        # This is an event we intercept to see when the task start.
        has_data = self._components.get(
            task._item.name(), {}
        ).get(task._preset.name())

        if not has_data:
            return

        render_data = has_data

        output_path = render_data['path']
        task._exportPath = output_path
        task.setDestinationDescription(output_path)
        # nullify path creation ? :\

    def publishResultComponent(self, render_task):
        # This is a task we intercept for each frame/item rendered.

        has_data = self._components.get(
            render_task._item.name(), {}
        ).get(render_task._preset.name())

        if not has_data:
            return

        render_data = has_data

        component = render_data['component']
        publish_path = render_data['path']
        is_published = render_data['published']

        if render_task.error():
            self.logger.warning('An Error occurred while rendering: {0}'.format(publish_path))
            return

        if is_published:
            return

        start, end = render_task.outputRange(clampToSource=False)
        start_handle, end_handle = render_task.outputHandles()

        fps = None
        if render_task._sequence:
            fps = render_task._sequence.framerate().toFloat()

        elif render_task._clip:
            fps = render_task._clip.framerate().toFloat()

        parent = component['version']['task']['parent']

        attributes = parent['custom_attributes']

        for attr_name, attr_value in attributes.items():
            if start and attr_name == 'fstart':
                attributes['fstart'] = str(start)

            if end and attr_name == 'fend':
                attributes['fend'] = str(end)

            if fps and attr_name == 'fps':
                attributes['fps'] = str(fps)

            if start_handle and attr_name == 'handles':
                attributes['handles'] = str(start_handle)

        if '#' in publish_path:
            # todo: Improve this logic
            publish_path = '{0} [{1}-{2}]'.format(publish_path, start, end)

        self.session.create(
            'ComponentLocation', {
                'location_id': self.ftrack_location['id'],
                'component_id': component['id'],
                'resource_identifier': publish_path
            }
        )
        self.logger.debug('Publishing : {0}'.format(publish_path))

        # Add option to publish or not the thumbnail.
        if self._preset.properties()['ftrack'].get('opt_publish_thumbnail'):
            self.publishThumbnail(component, render_task)

        # Add option to publish or not the reviewable.
        if self._preset.properties()['ftrack'].get('opt_publish_reviewable'):
            _, ext = os.path.splitext(publish_path)
            if ext == '.mov':
                component['version'].encode_media(publish_path)

        self.session.commit()
        render_data['published'] = True

    def publishThumbnail(self, component, render_task):
        source = render_task._clip
        thumbnail_qimage = source.thumbnail(source.posterFrame())
        thumbnail_file = tempfile.NamedTemporaryFile(prefix='hiero_ftrack_thumbnail', suffix='.png', delete=False).name
        thumbnail_qimage_resized = thumbnail_qimage.scaledToWidth(1280, QtCore.Qt.SmoothTransformation)
        thumbnail_qimage_resized.save(thumbnail_file)
        version = component['version']
        version.create_thumbnail(thumbnail_file)
        version['task'].create_thumbnail(thumbnail_file)

    def validateFtrackProcessing(self, exportItems):
        self._validate_project_progress_widget = foundry.ui.ProgressTask('Validating settings.')

        task_tags = set()
        task_types = self.schema.get_types('Task')

        processor_schema = self._preset.properties()['ftrack']['project_schema']
        task_type = self._preset.properties()['ftrack']['task_type']
        asset_type_code = self._preset.properties()['ftrack']['asset_type_code']
        asset_name = self._preset.properties()['ftrack']['asset_name']

        errors = {}
        missing_assets_type = []

        numitems = len(self._exportTemplate.flatten()) + len(exportItems)
        progress_index = 0
        for exportItem in exportItems:

            item = exportItem.item()

            if not hasattr(item, 'tags'):
                continue

            for tag in item.tags():
                meta = tag.metadata()
                if meta.hasKey('type') and meta.value('type') == 'ftrack':
                    task_name = meta.value('ftrack.name')
                    filtered_task_types = [task_type for task_type in task_types if task_type['name'] == task_name]
                    if len(filtered_task_types) == 1:
                        task_tags.add(task_name)

            for (exportPath, preset) in self._exportTemplate.flatten():
                progress_index += 1
                self._validate_project_progress_widget.setProgress(int(100.0 * (float(progress_index) / float(numitems))))

                # propagate properties from processor to tasks.
                preset.properties()['ftrack']['project_schema'] = processor_schema
                preset.properties()['ftrack']['task_type'] = task_type
                preset.properties()['ftrack']['asset_type_code'] = asset_type_code
                preset.properties()['ftrack']['asset_name'] = asset_name

                asset_type_code = preset.properties()['ftrack']['asset_type_code']

                ftrack_asset_type = self.session.query(
                    'AssetType where short is "{0}"'.format(asset_type_code)
                ).first()

                if not ftrack_asset_type and asset_type_code not in missing_assets_type:
                    missing_assets_type.append(asset_type_code)

                try:
                    result = getattr(self, 'task_type')
                except FtrackProcessorValidationError as error:
                    preset_errors = errors.setdefault(self, {})
                    preset_errors.setdefault('task_type', list(task_tags))

        self._validate_project_progress_widget = None

        if errors or missing_assets_type:
            settings_validator = FtrackSettingsValidator(self.session, errors, missing_assets_type)

            if settings_validator.exec_() != QtWidgets.QDialog.Accepted:
                return False

            self.validateFtrackProcessing(exportItems)

        return True


class FtrackProcessorUI(FtrackBase):

    def __init__(self, preset):
        super(FtrackProcessorUI, self).__init__(preset)
        self._nodeSelectionWidget = None

        # Variable placeholders for ui fragments.
        self.project_options = None
        self.schema_options = None
        self.task_type_options = None
        self.asset_name_options = None
        self.thumbnail_options = None
        self.reviewable_options = None
        self.asset_type_options = None

    def add_project_options(self, parent_layout):
        project_name = self._project.name()
        self.ftrack_project_exists = self.session.query(
            'select project_schema.name from Project where name is "{0}"'.format(project_name)
        ).first()

        update_or_create = 'Create'
        if self.ftrack_project_exists:
            update_or_create = 'Update'

        key, value, label = 'project_name', project_name, '{0} Project'.format(update_or_create)
        tooltip = 'Updating/Creating Project.'

        self.project_options = UIPropertyFactory.create(
            type(value),
            key=key,
            value=value,
            dictionary={},
            label=label + ':',
            tooltip=tooltip
        )
        self.project_options.setDisabled(True)
        parent_layout.addRow(label + ':', self.project_options)

    def add_project_scheme_options(self, parent_layout):

        schemas = self.session.query('ProjectSchema').all()
        schemas_name = [schema['name'] for schema in schemas]

        key, value, label = 'project_schema', schemas_name, 'Project Schema'
        tooltip = 'Select project schema.'

        self.schema_options = UIPropertyFactory.create(
            type(value),
            key=key,
            value=value,
            dictionary=self._preset.properties()['ftrack'],
            label=label + ':',
            tooltip=tooltip
        )
        parent_layout.addRow(label + ':', self.schema_options)

        if self.ftrack_project_exists:
            # If a project exist , disable the widget and set the previous schema found.
            schema_index = self.schema_options._widget.findText(self.ftrack_project_exists['project_schema']['name'])
            self.schema_options._widget.setCurrentIndex(schema_index)
            self.schema_options.setDisabled(True)

    def add_task_type_options(self, parent_layout, exportItems):

        # provide access to tags.
        task_tags = set()
        for exportItem in exportItems:
            item = exportItem.item()
            if not hasattr(item, 'tags'):
                continue

            for tag in item.tags():
                meta = tag.metadata()
                if meta.hasKey('type') and meta.value('type') == 'ftrack':
                    task_name = meta.value('ftrack.name')
                    task_tags.add(task_name)

        task_tags = list(task_tags) or [self._preset.properties()['ftrack']['task_type']]
        key, value, label = 'task_type', list(task_tags), 'Publish to Task'
        tooltip = 'Select a task to publish to.'

        self.task_type_options = UIPropertyFactory.create(
            type(value),
            key=key,
            value=value,
            dictionary=self._preset.properties()['ftrack'],
            label=label + ':',
            tooltip=tooltip
        )
        parent_layout.addRow(label + ':', self.task_type_options)

    def add_asset_name_options(self, parent_layout):

        asset_name = self._preset.properties()['ftrack']['asset_name']
        key, value, label = 'asset_name', asset_name, 'Set asset name as'
        tooltip = 'Select an asset name to publish to.'
        self.asset_name_options = UIPropertyFactory.create(
            type(value),
            key=key,
            value=value,
            dictionary=self._preset.properties()['ftrack'],
            label=label + ':',
            tooltip=tooltip
        )
        parent_layout.addRow(label + ':', self.asset_name_options)

    def add_thumbnail_options(self, parent_layout):

        # Thumbanil generation.
        key, value, label = 'opt_publish_thumbnail', True, 'Publish Thumbnail'
        tooltip = 'Generate and upload thumbnail'

        self.thumbnail_options = UIPropertyFactory.create(
            type(value),
            key=key,
            value=value,
            dictionary=self._preset.properties()['ftrack'],
            label=label + ':',
            tooltip=tooltip
        )
        parent_layout.addRow(label + ':', self.thumbnail_options)

    def add_reviewable_options(self, parent_layout):

        key, value, label = 'opt_publish_reviewable', True, 'Publish Reviewable'
        tooltip = 'Upload reviewable'

        self.reviewable_options = UIPropertyFactory.create(
            type(value),
            key=key,
            value=value,
            dictionary=self._preset.properties()['ftrack'],
            label=label + ':',
            tooltip=tooltip
        )
        parent_layout.addRow(label + ':', self.reviewable_options)

    def add_asset_type_options(self, parent_layout):

        asset_types = self.session.query(
            'AssetType'
        ).all()

        asset_type_names = [asset_type['short'] for asset_type in asset_types]
        key, value, label = 'asset_type_code', asset_type_names, 'Asset Type'
        tooltip = 'Asset type to be created.'

        self.asset_type_options = UIPropertyFactory.create(
            type(value),
            key=key,
            value=value,
            dictionary=self._preset.properties()['ftrack'],
            label=label + ':',
            tooltip=tooltip
        )
        parent_layout.addRow(label + ':', self.asset_type_options)

    def set_ui_tweaks(self):
        # Hide project path selector Foundry ticket : #36074
        for widget in self._exportStructureViewer.findChildren(QtWidgets.QWidget):
            if (
                    (isinstance(widget, QtWidgets.QLabel) and widget.text() == 'Export To:') or
                    widget.toolTip() == 'Export root path'
            ):
                widget.hide()

            if (isinstance(widget, QtWidgets.QLabel) and widget.text() == 'Export Structure:'):
                widget.hide()

    def addFtrackProcessorUI(self, widget, exportItems):
        form_layout = TaskUIFormLayout()
        layout = widget.layout()
        layout.addLayout(form_layout)
        form_layout.addDivider('Ftrack Options')

        self.add_project_options(form_layout)
        self.add_project_scheme_options(form_layout)
        self.add_task_type_options(form_layout, exportItems)
        self.add_asset_type_options(form_layout)
        self.add_asset_name_options(form_layout)
        self.add_thumbnail_options(form_layout)
        self.add_reviewable_options(form_layout)
        self.set_ui_tweaks()

