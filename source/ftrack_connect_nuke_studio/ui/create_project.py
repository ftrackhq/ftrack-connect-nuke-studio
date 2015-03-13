# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

import tempfile
import ftrack
import getpass
import hiero
import nuke

import FnAssetAPI.logging
from FnAssetAPI.ui.toolkit import QtGui, QtCore

from .widget import Resolution, Fps, Workflow

from ftrack_connect import worker
import ftrack_connect.ui.widget.header

from ftrack_connect_nuke_studio.ui.helper import (
    tree_data_factory,
    TagTreeOverlay,
    time_from_track_item,
    timecode_from_track_item,
    source_from_track_item,
    is_valid_tag_structure
)

from ftrack_connect_nuke_studio.ui.tag_tree_model import TagTreeModel
from ftrack_connect_nuke_studio.ui.tag_item import TagItem
from ftrack_connect_nuke_studio.processor import config
import ftrack_connect_nuke_studio
from ftrack_connect.ui.theme import applyTheme
from ftrack_connect_nuke_studio.exporter import export

class FTrackServerHelper(object):
    '''Handle interaction with ftrack server.'''

    def __init__(self):
        '''Initiate ftrack server helper and pre load data.'''
        self.server = ftrack.xmlServer
        self.workflows = [item.get('name')
                          for item in ftrack.getProjectSchemes()]
        self.tasktypes = dict((k.get('name'), k.get('typeid'))
                              for k in ftrack.getTaskTypes())

    def get_project_schema(self, name):
        '''Return project schema based on project *name*.'''
        data = {'type': 'frompath', 'path': name}
        project = self.server.action('get', data)
        scheme_id = project.get('projectschemeid')
        scheme_data = {'type': 'project_scheme', 'id': scheme_id}
        schema = self.server.action('get', scheme_data)
        return schema.get('name')

    def get_project_meta(self, name, keys):
        '''Return meta data with *keys* from project *name*.'''
        data = {'type': 'frompath', 'path': name}
        project = self.server.action('get', data)
        show_id = project.get('showid')
        result = {}
        for key in keys:
            value = self.get_metadata(show_id, key)
            result[key] = value
        return result

    def create_project(self, name, workflow='VFX Scheme'):
        '''Create a show with the given *name*, and the given *workflow*.'''
        schema_data = {'type': 'projectschemes'}
        schema_response = self.server.action('get', schema_data)
        workflow_ids = [
            result.get('schemeid')
            for result in schema_response if result.get('name') == workflow
        ]

        if not workflow_ids:
            return

        workflow_id = workflow_ids[0]

        data = {
            'type': 'show',
            'projectschemeid': workflow_id,
            'fullname': name,
            'name': name
        }

        response = self.server.action('create', data)
        return (response.get('showid'), 'show')

    def get_metadata(self, entity_id, key):
        '''Return metadata for *entity_id* and *keys*.'''
        data = {'type': 'meta', 'id': entity_id, 'key': key}
        response = self.server.action('get', data)
        return response

    def add_metadata(self, entity_type, entity_id, metadata):
        '''Add *metadata* to entity with *entity_type* and *entity_id*.'''
        for data_key, data_value in metadata.items():
            data = {
                'type': 'meta',
                'object': entity_type,
                'id': entity_id,
                'key': data_key,
                'value': data_value}

            self.server.action('set', data)

    def set_entity_data(self, entity_type, entity_id, trackItem,  start, end,
        resolution, fps, handles
    ):
        '''Populate data of the given *entity_id* and *entity_type*.'''
        data = {
            'fstart': start,
            'fend': end,
            'fps': fps,
            'resolution': '%sx%s' % (resolution.width(), resolution.height()),
            'handles': handles
        }

        in_src, out_src, in_dst, out_dst = timecode_from_track_item(trackItem)
        source = source_from_track_item(trackItem)

        metadata = {
            'time code src In': in_src,
            'time code src Out': out_src,
            'time code dst In': in_dst,
            'time code dst Out': out_src,
            'source material': source
        }

        attributes = {
            'type': 'set',
            'object': entity_type,
            'id': entity_id,
            'values': data
        }

        attribute_response = self.server.action('set', attributes)
        self.add_metadata(entity_type, entity_id, metadata)

        return attribute_response

    def _delete_asset(self, asset_id):
        '''Delete the give *asset_id*.'''
        asset_data = {
            'type': 'delete',
            'entityType': 'asset',
            'entityId': asset_id,
        }
        try:
            self.server.action('set', asset_data)
        except ftrack.FTrackError as error:
            FnAssetAPI.logging.debug(error)

    def _rename_asset(self, asset_id, name):
        '''Rename the give *asset_id* with the given *name*'''
        asset_data = {
            'type': 'set',
            'object': 'asset',
            'id': asset_id,
            'values': {'name': name}
        }
        try:
            self.server.action('set', asset_data)
        except ftrack.FTrackError as error:
            FnAssetAPI.logging.debug(error)
            return

    def create_asset(self, name, parent):
        '''Create asset with the give *name* and with the given *parent*.'''
        parent_id, parent_type = parent

        asset_type = 'img'

        asset_data = {
            'type': 'asset',
            'parent_id': parent_id,
            'parent_type': parent_type,
            'name': name,
            'assetType': asset_type
        }
        asset_response = self.server.action('create', asset_data)
        return asset_response

    def create_asset_version(self, asset_id, parent):
        '''Create an asset version linked to the *asset_id* and *parent*.

        *parent* must be a task.

        '''
        parent_id, parent_type = parent
        version_data = {
            'type': 'assetversion',
            'assetid': asset_id,
            'taskid': parent_id,
            'comment': '',
            'ispublished': True
        }

        version_response = self.server.action('create', version_data)
        version_id = version_response.get('versionid')
        self.server.action(
            'commit', {'type': 'assetversion', 'versionid': version_id}
        )
        return version_id

    def create_entity(self, entity_type, name, parent):
        '''Create entity on *parent* with *entity_type* and *name*.'''
        parent_id, parent_type = parent
        typeid = self.tasktypes.get(name)

        data = {
            'type': entity_type,
            'parent_id': parent_id,
            'parent_type': parent_type,
            'name': name,
            'typeid': typeid
        }
        response = self.server.action('create', data)
        return response.get('taskid'), 'task'

    #: TODO: Not sure how this is supposed to work. Consider removing it if
    # not used.
    def check_permissions(self, username=None):
        '''Check the permission level of the given named user.'''

        allowed = ['Administrator']

        username = username or getpass.getuser()

        user_data = {
            'type': 'user',
            'id': username
        }
        try:
            user_response = self.server.action('get', user_data)
            user_id = user_response.get('userid')
            role_data = {
                'type': 'roles',
                'userid': user_id
            }
            role_response = self.server.action('get ', role_data)
            roles = [role.get('name') for role in role_response]
            # requires a better understanding of relation between show and
            # roles.
            return True

        except Exception as error:
            FnAssetAPI.logging.debug(error)
            return False


class ProjectTreeDialog(QtGui.QDialog):
    '''Create project dialog.'''

    processor_ready = QtCore.Signal(object)

    def __init__(self, data=None, parent=None):
        '''Initiate dialog and create ui.'''
        super(ProjectTreeDialog, self).__init__(parent=parent)
        self.server_helper = FTrackServerHelper()
        applyTheme(self, 'integration')
        #: TODO: Consider if these permission checks are required.
        # user_is_allowed = self.server_helper.check_permissions()
        # if not user_is_allowed:
        #     FnAssetAPI.logging.warning(
        #         'The user does not have enough permissions to run this application.'
        #         'please check with your administrator your roles and permission level.'
        #     )
        #     return

        self.create_ui_widgets()
        self.processors = config()
        self.data = data
        self.setWindowTitle('Create ftrack project')
        self.logo_icon = QtGui.QIcon(':ftrack/image/dark/ftrackLogoColor')
        self.setWindowIcon(self.logo_icon)

        # Create tree model with fake tag.
        fake_root = TagItem({})
        self.tag_model = TagTreeModel(tree_data=fake_root, parent=self)

        # Set the data tree asyncronus.
        self.worker = worker.Worker(tree_data_factory, [self.data])
        self.worker.finished.connect(self.on_set_tree_root)
        self.project_worker = None

        # Create overlay.
        self.busy_overlay = TagTreeOverlay(self)
        self.busy_overlay.hide()

        # Set model to the tree view.
        self.tree_view.setModel(self.tag_model)
        self.tree_view.setAnimated(True)
        self.tree_view.header().setResizeMode(
            QtGui.QHeaderView.ResizeMode.ResizeToContents)

        # Connect signals.
        self.create_project_button.clicked.connect(self.on_create_project)
        self.close_button.clicked.connect(self.on_close_dialog)

        self.tree_view.selectionModel().selectionChanged.connect(
            self.on_tree_item_selection
        )
        self.worker.started.connect(self.busy_overlay.show)
        self.worker.finished.connect(self.on_project_preview_done)
        self.tag_model.project_exists.connect(self.on_project_exists)
        self.start_frame_offset_spinbox.valueChanged.connect(self._refresh_tree)
        self.handles_spinbox.valueChanged.connect(self._refresh_tree)
        self.processor_ready.connect(self.on_processor_ready)

        # Validate tag structure and set warning if there are any errors.
        tag_strucutre_valid, reason = is_valid_tag_structure(self.data)
        if not tag_strucutre_valid:
            self.header.setMessage(reason, 'warning')
            self.create_project_button.setEnabled(False)
        else:
            self.setDisabled(True)

            # Start populating the tree.
            self.worker.start()

    def create_ui_widgets(self):
        '''Setup ui for create dialog.'''
        self.resize(1024, 640)

        self.main_vertical_layout = QtGui.QVBoxLayout(self)
        self.setLayout(self.main_vertical_layout)
        self.header = ftrack_connect.ui.widget.header.Header(
            getpass.getuser(), self
        )
        self.main_vertical_layout.addWidget(self.header)

        self.central_horizontal_widget = QtGui.QWidget()
        self.central_horizontal_layout = QtGui.QHBoxLayout()
        self.central_horizontal_widget.setLayout(
            self.central_horizontal_layout
        )
        self.main_vertical_layout.addWidget(
            self.central_horizontal_widget, stretch=1
        )
        # create a central widget where to contain settings group and tree

        self.splitter = QtGui.QSplitter(self)
        self.central_widget = QtGui.QWidget(self.splitter)
        self.central_layout = QtGui.QVBoxLayout()
        self.central_widget.setLayout(self.central_layout)
        self.central_horizontal_layout.addWidget(self.central_widget, stretch=2)

        # settings
        self.group_box = QtGui.QGroupBox('General Settings')
        self.group_box.setMaximumSize(QtCore.QSize(16777215, 200))

        self.group_box_layout = QtGui.QVBoxLayout(self.group_box)

        self.workflow_layout = QtGui.QHBoxLayout()

        self.label = QtGui.QLabel('Workflow', parent=self.group_box)
        self.workflow_layout.addWidget(self.label)

        self.workflow_combobox = Workflow(self.group_box)
        self.workflow_layout.addWidget(self.workflow_combobox)

        self.group_box_layout.addLayout(self.workflow_layout)

        self.line = QtGui.QFrame(self.group_box)
        self.line.setFrameShape(QtGui.QFrame.HLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)
        self.group_box_layout.addWidget(self.line)

        self.resolution_layout = QtGui.QHBoxLayout()

        self.resolution_label = QtGui.QLabel('Resolution', parent=self.group_box)
        self.resolution_layout.addWidget(self.resolution_label)

        self.resolution_combobox = Resolution(self.group_box)
        self.resolution_layout.addWidget(self.resolution_combobox)
        self.group_box_layout.addLayout(self.resolution_layout)

        self.label_layout = QtGui.QHBoxLayout()

        self.fps_label = QtGui.QLabel('Frames Per Second', parent=self.group_box)
        self.label_layout.addWidget(self.fps_label)

        self.fps_combobox = Fps(self.group_box)
        self.label_layout.addWidget(self.fps_combobox)

        self.group_box_layout.addLayout(self.label_layout)

        self.handles_layout = QtGui.QHBoxLayout()

        self.handles_label = QtGui.QLabel('Handles', parent=self.group_box)
        self.handles_layout.addWidget(self.handles_label)

        self.handles_spinbox = QtGui.QSpinBox(self.group_box)
        self.handles_spinbox.setProperty('value', 5)
        self.handles_layout.addWidget(self.handles_spinbox)

        self.group_box_layout.addLayout(self.handles_layout)

        self.start_frame_offset_layout = QtGui.QHBoxLayout()

        self.start_frame_offset_label = QtGui.QLabel(
            'Start frame offset', parent=self.group_box
        )
        self.start_frame_offset_layout.addWidget(self.start_frame_offset_label)

        self.start_frame_offset_spinbox = QtGui.QSpinBox(self.group_box)
        self.start_frame_offset_spinbox.setMaximum(9999)
        self.start_frame_offset_spinbox.setProperty('value', 1001)
        self.start_frame_offset_layout.addWidget(self.start_frame_offset_spinbox)
        self.group_box_layout.addLayout(self.start_frame_offset_layout)

        self.central_layout.addWidget(self.group_box)

        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.tree_view = QtGui.QTreeView()
        self.central_layout.addWidget(self.tree_view)

        self.tool_box = QtGui.QToolBox(self.splitter)

        default_message = QtGui.QTextEdit('Make a selection to see the available properties')
        default_message.readOnly = True
        default_message.setAlignment(QtCore.Qt.AlignCenter)
        self.tool_box.addItem(default_message , 'Processors')
        self.tool_box.setContentsMargins(0, 15, 0, 0)
        self.tool_box.setMinimumSize(QtCore.QSize(300, 0))
        self.tool_box.setFrameShape(QtGui.QFrame.StyledPanel)

        self.central_horizontal_layout.addWidget(self.splitter, stretch=1)

        self.bottom_button_layout = QtGui.QHBoxLayout()
        self.main_vertical_layout.addLayout(self.bottom_button_layout)

        self.close_button = QtGui.QPushButton('Close', parent=self)
        self.bottom_button_layout.addWidget(self.close_button)

        self.create_project_button = QtGui.QPushButton('Create', parent=self)
        self.bottom_button_layout.addWidget(self.create_project_button)

        QtCore.QMetaObject.connectSlotsByName(self)

    def on_project_exists(self, name):
        '''Handle on project exists signal.'''
        if self.workflow_combobox.isEnabled():
            schema = self.server_helper.get_project_schema(name)
            index = self.workflow_combobox.findText(schema)
            self.workflow_combobox.setCurrentIndex(index)
            self.workflow_combobox.setDisabled(True)

            project_metadata = self.server_helper.get_project_meta(
                name, ['fps', 'resolution', 'offset', 'handles'])
            fps = project_metadata.get('fps')
            handles = project_metadata.get('handles')
            offset = project_metadata.get('offset')
            resolution = project_metadata.get('resolution')

            self.resolution_combobox.setCurrentFormat(resolution)

            fps_index = self.fps_combobox.findText(fps)
            self.fps_combobox.setCurrentIndex(fps_index)

            self.handles_spinbox.setValue(int(handles))

            self.start_frame_offset_spinbox.setValue(int(offset))

    def on_project_preview_done(self):
        '''Handle signal once the project preview have started populating.'''
        self.setEnabled(True)

    def on_processor_ready(self, args):
        '''Handle processor ready signal.'''
        plugins = ftrack_connect_nuke_studio.PROCESSOR_PLUGINS
        processor = args[0]
        data = args[1]

        track_item = data.get('application_object')
        FnAssetAPI.logging.info(track_item)
        nuke_script_path = None
        if track_item:
            nuke_script_path = export(track_item)
            FnAssetAPI.logging.info('RESULT NUKE PATH : %s' % nuke_script_path)
            data.pop('application_object')
            # FROM HERE THE RESULT SCRIPT SHOULD BE PASSET TO PROCESSOR.script
            # AND LET IT RENDER IT OUT.

        plugin = plugins.get(processor)
        if nuke_script_path:
            # inject the script in the processor
            # restrict to one only for test purposes
            plugin.script = nuke_script_path.get('comp')

        plugin.process(data)

    def on_set_tree_root(self):
        '''Handle signal and populate the tree.'''
        self.busy_overlay.hide()
        self.create_project_button.setEnabled(True)
        self.tag_model.setRoot(self.worker.result)

    def on_tree_item_selection(self, selected, deselected):
        '''Handle signal triggered when a tree item gets selected.'''
        self._reset_processors()

        index = selected.indexes()[0]
        item = index.model().data(index, role=self.tag_model.ITEM_ROLE)
        processor = self.processors.get(item.name)

        if not processor:
            return

        asset_names = processor.keys()
        for asset_name in asset_names:
            widget = QtGui.QWidget()
            layout = QtGui.QVBoxLayout()
            widget.setLayout(layout)

            for component_name, component_fn in processor[asset_name].items():

                data = QtGui.QGroupBox(component_name)
                data_layout = QtGui.QVBoxLayout()
                data.setLayout(data_layout)

                layout.addWidget(data)
                for node_name, knobs in component_fn.defaults.items():
                    for knob, knob_value in knobs.items():
                        knob_layout = QtGui.QHBoxLayout()
                        label = QtGui.QLabel('%s:%s' % (node_name, knob))
                        value = QtGui.QLineEdit(str(knob_value))
                        value.setDisabled(True)
                        knob_layout.addWidget(label)
                        knob_layout.addWidget(value)
                        data_layout.addLayout(knob_layout)

            self.tool_box.addItem(widget, asset_name)

    def on_close_dialog(self):
        '''Handle signal trigged when close dialog button is pressed.'''
        self.reject()

    def on_create_project(self):
        '''Handle signal triggered when the create project button gets pressed.'''
        QtGui.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.WaitCursor)
        )
        self.setDisabled(True)

        items = self.tag_model.root.children
        self.project_worker = worker.Worker(
            self.create_project, (items, self.tag_model.root)
        )
        self.project_worker.finished.connect(self.on_project_created)
        self.project_worker.finished.connect(self.busy_overlay.hide)
        self.project_worker.start()
        self.busy_overlay.show()

        while self.project_worker.isRunning():
            app = QtGui.QApplication.instance()
            app.processEvents()

        if self.project_worker.error:
            raise self.project_worker.error[1], None, self.project_worker.error[2]

    def on_project_created(self):
        '''Handle signal triggered when the project creation finishes.'''
        information = (
            'The project has now been created\nPlease wait for '
            'the background processes to finish.'
        )

        QtGui.QApplication.restoreOverrideCursor()
        self.header.setMessage(
            'The project has been succesfully created !', 'info'
        )
        self.setDisabled(False)

    def _refresh_tree(self):
        '''Refresh tree.'''
        self.tag_model.dataChanged.emit(
            QtCore.QModelIndex(), QtCore.QModelIndex()
        )

    def _reset_processors(self):
        '''Reset the processor widgets.'''
        while self.tool_box.count() > 0:
            self.tool_box.removeItem(0)

    def create_project(self, data, previous=None):
        '''Recursive function to create a new ftrack project on the server.'''
        selected_workflow = self.workflow_combobox.currentText()
        for datum in data:
            # Gather all the useful informations from the track
            track_in = int(datum.track.source().sourceIn())
            track_out = int(datum.track.source().sourceOut())
            # NOTE: effectTrack are not used atm
            effects = [
                effect for effect in datum.track.linkedItems()
                if isinstance(effect, hiero.core.EffectTrackItem)
            ]

            if datum.track.source().mediaSource().singleFile():
                # Adjust frame in and out if the media source is a single file.
                # This fix is required because Hiero is reporting Frame in as 0
                # for a .mov file while Nuke is expecting Frame in 1.
                track_in += 1
                track_out += 1
                FnAssetAPI.logging.debug(
                    'Single file detected, adjusting frame start and frame end '
                    'to {0}-{1}'.format(track_in, track_out)
                )

            source = source_from_track_item(datum.track)
            start, end, in_, out = time_from_track_item(datum.track, self)
            fps = self.fps_combobox.currentText()
            resolution = self.resolution_combobox.currentFormat()
            offset = self.start_frame_offset_spinbox.value()
            handles = self.handles_spinbox.value()

            if datum.type == 'show':
                if datum.exists:
                    FnAssetAPI.logging.debug('%s %s exists as %s, reusing it.' % (
                        datum.name, datum.type, datum.exists.get('showid')))
                    result = (datum.exists.get('showid'), 'show')
                else:
                    FnAssetAPI.logging.debug('creating show %s' % datum.name)
                    result = self.server_helper.create_project(
                        datum.name, selected_workflow)
                    datum.exists = {'showid': result[0]}

                show_meta = {
                    'fps': fps,
                    'resolution': str(resolution),
                    'offset': offset,
                    'handles': handles
                }

                self.server_helper.add_metadata(result[1], result[0], show_meta)

            else:
                if datum.exists:
                    FnAssetAPI.logging.debug('%s %s exists as %s, reusing it.' % (
                        datum.name, datum.type, datum.exists.get('taskid')))
                    result = (datum.exists.get('taskid'), 'task')
                else:
                    FnAssetAPI.logging.debug(
                        'creating %s %s' % (datum.type, datum.name))
                    try:
                        result = self.server_helper.create_entity(
                            datum.type, datum.name, previous)
                    except ftrack.api.ftrackerror.PermissionDeniedError as error:
                        datum.exists = 'error'
                        continue
                    datum.exists = {'taskid': result[0]}

                if datum.type == 'shot':
                    FnAssetAPI.logging.debug(
                        'Setting metadata to %s' % datum.name)
                    self.server_helper.set_entity_data(
                        result[1], result[0], datum.track,
                        start, end, resolution, fps, handles
                    )

                    datum.track.source().setEntityReference(
                        'ftrack://{0}?entityType={1}'.format(result[0], result[1])
                    )
                FnAssetAPI.logging.info('DATUM:%s' % datum)

                if datum.type == 'task':
                    processor = self.processors.get(datum.name)
                    if not processor:
                        FnAssetAPI.logging.debug(
                            'No processor available for task: %s' % datum.name
                        )
                        continue

                    asset_names = processor.keys()
                    for asset_name in asset_names:
                        asset = self.server_helper.create_asset(
                            asset_name, previous
                        )
                        asset_id = asset.get('assetid')

                        version_id = self.server_helper.create_asset_version(
                            asset_id, result
                        )

                        for component_name, component_fn in processor[asset_name].items():
                            out_data = {
                                'resolution': resolution,
                                'source_in': track_in,
                                'source_out': track_out,
                                'source_file': source,
                                'destination_in': start,
                                'destination_out': end,
                                'fps': fps,
                                'offset': offset,
                                'asset_version_id': version_id,
                                'component_name': component_name,
                                'handles': handles,
                                'application_object': datum.track
                            }
                            FnAssetAPI.logging.info(out_data)
                            processor_name = component_fn.getName()
                            data = (processor_name,  out_data)
                            self.processor_ready.emit(data)

            self._refresh_tree()

            if datum.children:
                self.create_project(datum.children, result)
