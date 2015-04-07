# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import urlparse

import FnAssetAPI.logging
import ftrack_legacy as ftrack
import clique


PLATE_ASSET_NAME = 'plate'
PLATE_COMPONENT_NAME = 'main'


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


class PublishPlates(object):
    '''Publish plates to ftrack.'''

    def launch(self, event):
        '''Publish plates to ftrack.'''
        FnAssetAPI.logging.debug('Publish plates {0}'.format(event))

        for track_item in event['data']['track_items']:
            reference = track_item.source().entityReference()

            if not reference:
                continue

            url = urlparse.urlparse(reference)
            shot_id = url.netloc

            shot = ftrack.Task(shot_id)
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
