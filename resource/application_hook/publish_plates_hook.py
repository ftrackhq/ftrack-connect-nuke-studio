# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import urlparse

import FnAssetAPI.logging
import ftrack_legacy as ftrack
import clique


PLATE_ASSET_NAME = 'plate'
PLATE_COMPONENT_NAME = 'main'


def get_ftrack_tag(tags, name):
    '''Return ftrack tag from *tags* matching *name*.'''
    for tag in tags:
        metadata = tag.metadata()
        if not metadata.hasKey('type') or metadata.value('type') != 'ftrack':
            continue
 
        # TODO: Stop this being hard coded.
        if metadata.value('ftrack.name') != name:
            continue
        
        return tag
    
    return None


def publish_plate(asset, track_item):
    FnAssetAPI.logging.debug(
        'Publish new version of {0} with track item {1}'.format(
            asset, track_item
        )
    )
    versions = asset.getVersions()

    task_id = None
    if versions:
        task_id = versions[-1].get('taskid')

    version = asset.createVersion(taskid=task_id)

    import ftrack_connect_nuke_studio.ui.helper
    source = ftrack_connect_nuke_studio.ui.helper.source_from_track_item(
        track_item
    )

    first = int(track_item.source().sourceIn())
    last = int(track_item.source().sourceOut())

    collection = clique.parse(
        source, '{head}{padding}{tail}'
    )
    collection.indexes.update(set(range(first, last + 1)))
    path = str(collection)

    component = version.createComponent(PLATE_COMPONENT_NAME, path)
    component.setMeta('img_main', True)

    version.publish()

    track_item.source().setEntityReference(component.getEntityRef())


class PublishPlates(object):
    '''Publish plates to ftrack.'''

    def launch(self, event):
        '''Publish plates to ftrack.'''
        FnAssetAPI.logging.debug('Publish plates {0}'.format(event))
        import hiero
        import ftrack_legacy

        # Find project tag.
        project_name = None
        bin = hiero.core.projects()[0].clipsBin()[1]
        project_version_item = bin.items()[0]
        #sequence = project_version_item.item()
        sequence = event['data']['track_items'][0].parent().parent()
        FnAssetAPI.logging.debug("Getting project tags from %s sequence %s" % (hiero.core.projects()[0], sequence))
        project_tag = get_ftrack_tag(sequence.tags(), 'project')
        if project_tag is not None:
            project_name = project_tag.metadata().value('tag.value')

        for track_item in event['data']['track_items']:
            # Find Shot from tag for now because entity reference lost by replace clip.
            # TODO: This needs rethinking as it is incredibly brittle!
            shot_name = None
            clip_tags = track_item.tags()
            FnAssetAPI.logging.debug("Getting shot tags")
            shot_tag = get_ftrack_tag(clip_tags, 'shot')
            if shot_tag is not None:
                shot_name = shot_tag.metadata().value('tag.value')

            if None in (project_name, shot_name):
                raise ValueError(
                    'Could not determine project name or shot name from track item {0}'
                    .format(track_item)       
                )
                
            shot = ftrack_legacy.getFromPath([project_name, shot_name])
            if not shot:
                raise ValueError(
                    'Could not fetch shot from ftrack for path {0} / {1}'
                    .format(project_name, shot_name)
                )

            assets = shot.getAssets(assetTypes=['img'])

            for asset in assets:
                if asset.getName().lower() == PLATE_ASSET_NAME:
                    publish_plate(asset, track_item)
                    break

    def register(self):
        '''Register hook.'''
        ftrack.EVENT_HUB.subscribe(
            'topic=ftrack.nukestudio.publish-plates',
            self.launch
        )


def register(registry, **kw):
    '''Register hooks for default fps setting.'''
    plugin = PublishPlates()
    plugin.register()

