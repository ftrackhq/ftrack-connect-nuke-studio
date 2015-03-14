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

    def __init__(self, entity_reference):
        '''Instansiate with *entity_reference* to assetize read node.'''
        # OriginalScriptWriter is not a  new-style class so constructor must be
        # called explicitly. 
        OriginalScriptWriter.__init__(self)
        self._entity_reference = entity_reference

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
            node.setKnob('file', self._entity_reference)

        elif node.type() == 'Write':
            newNode = hiero.core.nuke.Node('MyWrite', **node.knobs())
            node = newNode

        return node

    def writeToDisk(self, scriptFilename):
        '''Write the script to disk with *scriptFilename*.'''
        key = os.path.splitext(
            os.path.basename(scriptFilename))[0].split('_')[-2]
        self.result_outputs[key] = scriptFilename
        OriginalScriptWriter.writeToDisk(self, scriptFilename)


def export(trackItem, entity_reference,
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
    project = trackItem.project()
    project.setProjectRoot(tempfile.tempdir)

    # Replace the default ScriptWriter
    hiero.core.nuke.ScriptWriter = functools.partial(
        CustomScriptWriter, entity_reference
    )
    # Export the trackItem
    hiero.core.taskRegistry.createAndExecuteProcessor(
        preset,
        [hiero.core.ItemWrapper(trackItem)],
        synchronous=True
    )

    script_path_result = CustomScriptWriter.result_outputs

    # Restore the default ScriptWriter
    hiero.core.nuke.ScriptWriter = OriginalScriptWriter

    # return the destination path of the nuke script
    return script_path_result
