import hiero.core
import tempfile
import FnAssetAPI

OriginalScriptWriter = hiero.core.nuke.ScriptWriter

class CustomScriptWriter(OriginalScriptWriter):
  result_outputs = {}

  def __init__(self, entity_reference):
    OriginalScriptWriter.__init__(self)
    self.entity_reference = entity_reference


  def addNode(self, node):
    # List of nodes that should actually be added to the script
    nodesToAdd = []

    # node might actually be a list of nodes.  If it is, call onNodeAdded for each one
    if isinstance(node, hiero.core.nuke.Node):
      nodesToAdd.append( self.onNodeAdded(node) )
    else:
      try:
        for n in node:
          nodesToAdd.append( self.onNodeAdded(n) )
      except:
        pass

    # Call base class to add the node(s)
    OriginalScriptWriter.addNode(self, nodesToAdd)


  def onNodeAdded(self, node):
    """ Callback when a node is added. Return the node that should actually be added. """
    if node.type() == "Read":
      # print "CustomScriptWriter Read node added:", node.knob("file")
      # Replace the path with a Python expression
      # newFileKnobValue = "\\[python str('%s')\\]" %  node.knob("file")
      node.setKnob("file", self.entity_reference)

    elif node.type() == "Write":
      # print "CustomScriptWriter Write node added:", node.knob("file")
      # Replace the Write node with MyWrite, copying all the knob values
      newNode = hiero.core.nuke.Node("MyWrite", **node.knobs())
      node = newNode

    return node

  def writeToDisk(self, scriptFilename):
    """ Write the script. """
    FnAssetAPI.logging.info('SCRIPT NAME %s' % scriptFilename)
    self.result_outputs['script'] = scriptFilename
    OriginalScriptWriter.writeToDisk(self, scriptFilename)


def export(trackItem, presetName="Basic Nuke Shot With Annotations"):
  current_preset = None
  exportPresetName = presetName
  for preset in hiero.core.taskRegistry.localPresets():
    if preset.name() == exportPresetName:
      current_preset = preset
      break

  if not current_preset:
    raise ValueError('No preset found for name : %s !' % presetName)

  # Set the project root to a temp folder so we know where we output the files.
  project = trackItem.project()
  project.setProjectRoot( tempfile.tempdir )

  # get the entity reference to be used in the read node
  entity_reference =  trackItem.source().entityReference()

  script_writer = CustomScriptWriter
  def wrapCustomScriptWriter(*args, **kwargs):
    return script_writer(entity_reference=entity_reference)

  # Replace the default ScriptWriter
  hiero.core.nuke.ScriptWriter = wrapCustomScriptWriter
  # Export the trackItem
  hiero.core.taskRegistry.createAndExecuteProcessor(
    current_preset,
    [hiero.core.ItemWrapper(trackItem)],
    synchronous=True
  )

  script_path_result = script_writer.result_outputs['script']
  # Restore the default ScriptWriter
  hiero.core.nuke.ScriptWriter = OriginalScriptWriter

  # return the destination path of the nuke script
  return script_path_result




