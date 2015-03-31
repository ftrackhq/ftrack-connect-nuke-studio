# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import os
import tempfile
import functools

import hiero.core
import FnAssetAPI


OriginalScriptWriter = hiero.core.nuke.ScriptWriter


class CustomScriptWriter(OriginalScriptWriter):
    '''Custom script writer to assetize nodes.'''

    result_outputs = {}

    def __init__(self, read_node_data, pre_comp_node):
        '''Instansiate with *read_node_data* to assetize read node.'''
        # OriginalScriptWriter is not a  new-style class so constructor must be
        # called explicitly. 
        OriginalScriptWriter.__init__(self)
        self._read_node_data = read_node_data
        self._pre_comp_node = pre_comp_node

    def addNode(self, node):
        '''Add *node* to script.'''
        # List of nodes that should actually be added to the script.
        nodesToAdd = []

        # node might actually be a list of nodes.  If it is, call onNodeAdded
        # for each one.
        if isinstance(node, hiero.core.nuke.Node):
            nodesToAdd.append(self.onNodeAdded(node))
        else:
            try:
                for n in node:
                    nodesToAdd.append(self.onNodeAdded(n))
            except:
                pass

        # Call base class to add the node(s).
        OriginalScriptWriter.addNode(self, nodesToAdd)

    def onNodeAdded(self, node):
        '''Callback to return node to be added from *node*.'''
        if node.type() == 'Read':
            for name, value in self._read_node_data.iteritems():
                node.setKnob(name, value)

        if self._pre_comp_node and node.type() == 'Precomp':
            for name, value in self._pre_comp_node.iteritems():
                node.setKnob(name, value)

        # if node.type() == 'FrameRange':
        #     node.setKnob('first_frame', self._read_node_data['first'])
        #     node.setKnob('last_frame', self._read_node_data['last'])

        # :TODO: Handle write node if necessary.
        if node.type() == 'Write':
            node.setKnob('frame_mode', 'start at')
            node.setKnob('frame', self._read_node_data['first'])

        return node

    def writeToDisk(self, scriptFilename):
        '''Write the script to disk with *scriptFilename*.'''
        if '_comp_annotations_' in scriptFilename:
            key = 'annotations'
        else:
            key = 'comp'

        self.result_outputs[key] = scriptFilename
        OriginalScriptWriter.writeToDisk(self, scriptFilename)


def export(track_item, read_node_data, pre_comp_node=None,
    preset_name='Basic Nuke Shot With Annotations'
):
    preset = None
    for candidate_preset in hiero.core.taskRegistry.localPresets():
        if candidate_preset.name() == preset_name:
            preset = candidate_preset
            break

    if not preset:
        raise ValueError(
            'No preset found for name : {0} !'.format(preset_name)
        )

    # Set the project root to a temp folder so we know where we output the
    # files.
    project = track_item.project()
    project.setProjectRoot(tempfile.tempdir)

    # Replace the default ScriptWriter
    hiero.core.nuke.ScriptWriter = functools.partial(
        CustomScriptWriter, read_node_data, pre_comp_node
    )
    # Export the track_item
    hiero.core.taskRegistry.createAndExecuteProcessor(
        preset,
        [hiero.core.ItemWrapper(track_item)],
        synchronous=True
    )

    script_path_result = CustomScriptWriter.result_outputs

    # Restore the default ScriptWriter
    hiero.core.nuke.ScriptWriter = OriginalScriptWriter

    # return the destination path of the nuke script
    return script_path_result
