# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import urlparse
import pprint
import functools
import logging

import ftrack
import ftrack_api

import hiero


logger = logging.getLogger(__name__)


def _callback(item, ftrack_version):
    '''Find and set version on *item* based on *ftrack_version*.'''

    # Get all component ids on selected version to have something to compare
    # with. To speed this up consider pre-selecting the components and their
    # ids in the version query.
    component_ids = [
        component['id'] for component in ftrack_version['components']
    ]

    # Start at min version.
    item.minVersion()
    versions = [item.currentVersion()]

    nextVersion = item.nextVersion()
    while nextVersion:
        versions.append(nextVersion)
        nextVersion = item.nextVersion()

    for version in versions:
        clip = version.item()
        if clip:
            if hasattr(clip, 'entityReference'):
                reference = clip.entityReference()
                if reference and reference.startswith('ftrack://'):

                    # Parse the reference to get the id of the entity.
                    url = urlparse.urlparse(reference)

                    # Check if entityReference is a related component.
                    if url.netloc in component_ids:
                        item.setCurrentVersion(version)
                        break
    else:
        # If loop ends without break set the version to the latest since we
        # couldn't match any component id.
        item.maxVersion()


def callback(event):
    '''Handle version notification call to action.

    The callback will find the track item matching the version in any track
    and switch version.

    '''
    version_id = event['data']['version_id']

    logger.info('Update track to latest versions based on:\n{0}'.format(
        pprint.pformat(event['data']))
    )

    # TODO: Move these hooks to new API so that we don't need to recreate
    # the session.
    _session = ftrack_api.Session()

    version = _session.query(
        'select components, components.id from AssetVersion where id '
        'is "{0}"'.format(version_id)
    ).all()[0]

    related_components = _session.query(
        'select id from Component where '
        'version.asset.versions.id is "{0}"'.format(version_id)
    )

    related_component_ids = [
        component['id'] for component in related_components
    ]
    for item in hiero.core.findItems():

        # Only try to version up track items.
        if isinstance(item, hiero.core.TrackItem):

            # User the source to be able to match against entity reference.
            clip = item.source()
            if hasattr(clip, 'entityReference'):
                reference = clip.entityReference()
                if reference and reference.startswith('ftrack://'):

                    # Parse the reference to get the id of the entity.
                    url = urlparse.urlparse(reference)

                    # Check if entityReference is a related component.
                    if url.netloc in related_component_ids:

                        logger.info('Setting new version on "{0}"'.format(
                            str(item)
                        ))

                        # Use hiero version scanner to scan for new versions
                        # before switching to the wanted version to make sure
                        # that it exists in the stack.
                        hiero.ui.ScanForVersions.VersionScannerThreaded(
                        ).scanForVersions(
                            [item.maxVersion()],
                            functools.partial(_callback, item, version),
                            False
                        )


def register(registry, **kw):
    '''Register hook.'''

    # Validate that registry is instance of ftrack.Registry, if not
    # return early since the register method probably is called
    # from the new API.
    if not isinstance(registry, ftrack.Registry):
        return

    logger.info('Register version notification hook')

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.crew.notification.version',
        callback
    )
