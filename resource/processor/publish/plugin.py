# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

import os
import tempfile

import clique
import ftrack_legacy as ftrack

import ftrack_connect_nuke_studio.processor


class PublishPlugin(ftrack_connect_nuke_studio.processor.ProcessorPlugin):
    '''Publish component data.'''

    def __init__(self):
        '''Initialise processor.'''
        super(PublishPlugin, self).__init__()
        self.name = 'processor.publish'
        self.defaults = {
            'OUT': {
                'file_type': 'dpx',
                'afterRender': (
                    'from ftrack_connect_nuke_studio.nuke_publish_cb '
                    'import createComponent;'
                    'createComponent()'
                )
            }
         }
        self.script = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), 'script.nk'
            )
        )

    def prepare_data(self, data):
        '''Return data mapping processed from input *data*.'''
        data = super(PublishPlugin, self).prepare_data(data)

        # Define output file sequence.
        format = '.####.{0}'.format(data['OUT']['file_type'])
        name = self.name.replace('.', '_')
        temporary_path = tempfile.NamedTemporaryFile(
            prefix=name, suffix=format, delete=False
        )
        data['OUT']['file'] = temporary_path.name.replace('\\', '/')

        return data

    def process(self, data):
        '''Run script against *data*.'''
        print data
        asset_version_id = data['asset_version_id']

        first = int(data['source_in']) - int(data['handles'])
        last = int(data['source_out']) + int(data['handles'])

        version = ftrack.AssetVersion(asset_version_id)

        # Create the component and copy data to the most likely store
        component = data['component_name']

        filePath = data['source_file']
        try:
            collection = clique.parse(
                data['source_file'], '{head}{padding}{tail}'
            )
            collection.indexes.update(set(range(first, last + 1)))

            filePath = str(collection)
        except ValueError:
            # If value error is triggered we've encountered a path that is not
            # matching the required pattern. Use the original file path since
            # it is probably a single file.
            pass

        component = version.createComponent(component, filePath)
        component.setMeta('img_main', True)


def register(registry):
    '''Register plugin with *registry*.'''
    plugin_publish = PublishPlugin()
    registry.add(plugin_publish)
