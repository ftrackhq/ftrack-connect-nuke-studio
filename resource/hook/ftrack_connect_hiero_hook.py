# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

import os
import re
import getpass
import sys
import pprint
import logging

import ftrack_api
import ftrack_connect.application
import ftrack_connect_nuke_studio


FTRACK_CONNECT_HIERO_PATH = os.environ.get(
    'FTRACK_CONNECT_NUKE_STUDIO_PATH',
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), '..', 'nuke_studio'
        )
    )
)


class LaunchAction(object):
    '''ftrack connect legacy plugins discover and launch action.'''

    identifier = 'ftrack-connect-hiero-application'

    def __init__(self, applicationStore, launcher, session):
        '''Initialise action with *applicationStore* and *launcher*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        '''
        super(LaunchAction, self).__init__()

        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

        self.applicationStore = applicationStore
        self.launcher = launcher
        self.session = session

    def register(self):
        '''Override register to filter discover actions on logged in user.'''
        self.session.event_hub.subscribe(
            'topic=ftrack.action.discover and source.user.username={0}'.format(
                getpass.getuser()
            ),
            self.discover
        )

        self.session.event_hub.subscribe(
            'topic=ftrack.action.launch and source.user.username={0} '
            'and data.actionIdentifier={1}'.format(
                getpass.getuser(), self.identifier
            ),
            self.launch
        )

        self.session.event_hub.subscribe(
            'topic=ftrack.connect.plugin.debug-information',
            self.get_version_information
        )

    def discover(self, event):
        '''Return discovered applications.'''

        items = []
        applications = self.applicationStore.applications
        applications = sorted(
            applications, key=lambda application: application['label']
        )

        for application in applications:
            applicationIdentifier = application['identifier']
            label = application['label']
            items.append({
                'actionIdentifier': self.identifier,
                'label': label,
                'variant': application.get('variant', None),
                'description': application.get('description', None),
                'icon': application.get('icon', 'default'),
                'applicationIdentifier': applicationIdentifier
            })

        return {
            'items': items
        }

    def launch(self, event):
        '''Handle *event*.

        event['data'] should contain:

            *applicationIdentifier* to identify which application to start.

        '''
        # Prevent further processing by other listeners.
        event.stop()
        applicationIdentifier = (
            event['data']['applicationIdentifier']
        )

        context = event['data'].copy()
        context['source'] = event['source']

        applicationIdentifier = event['data']['applicationIdentifier']
        context = event['data'].copy()
        context['source'] = event['source']

        return self.launcher.launch(
            applicationIdentifier, context
        )

    def get_version_information(self, event):
        '''Return version information.'''
        return [
            dict(
                name='ftrack connect hiero',
                version=ftrack_connect_nuke_studio.__version__
            )
        ]


class ApplicationStore(ftrack_connect.application.ApplicationStore):
    '''Discover and store available applications on this host.'''

    def _discoverApplications(self):
        '''Return a list of applications that can be launched from this host.

        An application should be of the form:

            dict(
                'identifier': 'name_version',
                'label': 'Name',
                'variant': 'version',
                'description': 'description',
                'path': 'Absolute path to the file',
                'version': 'Version of the application',
                'icon': 'URL or name of predefined icon'
            )

        '''
        applications = []

        if sys.platform == 'darwin':
            prefix = ['/', 'Applications']

            applications.extend(self._searchFilesystem(
                versionExpression=r'Hiero(?P<version>.*)\/.+$',
                expression=prefix + ['Hiero\d.+', 'Hiero\d.+.app'],
                label='Hiero',
                variant='{version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero'
            ))

            applications.extend(self._searchFilesystem(
                versionExpression=r'Nuke(?P<version>.*)\/.+$',
                expression=prefix + ['Nuke.*', 'Hiero\d[\w.]+.app'],
                label='Hiero',
                variant='{version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero'
            ))

        elif sys.platform == 'win32':
            prefix = ['C:\\', 'Program Files.*']

            applications.extend(self._searchFilesystem(
                expression=prefix + ['Hiero\d.+', 'hiero.exe'],
                label='Hiero',
                variant='{version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero'
            ))

            # Somewhere along the way The Foundry changed the default install directory.
            # Add the old directory as expression to find old installations of Hiero
            # as well.
            #
            # TODO: Refactor this once ``_searchFilesystem`` is more sophisticated.
            applications.extend(self._searchFilesystem(
                expression=prefix + ['The Foundry', 'Hiero\d.+', 'hiero.exe'],
                label='Hiero',
                variant='{version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero'
            ))

            version_expression = re.compile(
                r'Nuke(?P<version>[\d.]+[\w\d.]*)'
            )

            applications.extend(self._searchFilesystem(
                expression=prefix + ['Nuke.*', 'Nuke\d.+.exe'],
                versionExpression=version_expression,
                label='Hiero',
                variant='{version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero',
                launchArguments=['--hiero']
            ))

        elif sys.platform == 'linux2':
            applications.extend(self._searchFilesystem(
                versionExpression=r'Hiero(?P<version>.*)\/.+\/.+$',
                expression=['/', 'usr', 'local', 'Hiero.*', 'bin', 'Hiero\d.+'],
                label='Hiero',
                variant='{version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero'
            ))

            applications.extend(self._searchFilesystem(
                expression=['/', 'usr', 'local', 'Nuke.*', 'Nuke\d.+'],
                label='Hiero',
                variant='{version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero',
                launchArguments=['--hiero']
            ))

        self.logger.debug(
            'Discovered applications:\n{0}'.format(
                pprint.pformat(applications)
            )
        )

        return applications


class ApplicationLauncher(
    ftrack_connect.application.ApplicationLauncher
):
    '''Launch applications with legacy plugin support.'''

    def _getApplicationEnvironment(self, application, context):
        '''Modify and return environment with legacy plugins added.'''
        environment = super(
            ApplicationLauncher, self
        )._getApplicationEnvironment(
            application, context
        )

        hiero_plugin_path = os.path.join(
            FTRACK_CONNECT_HIERO_PATH, 'plugin'
        )

        environment = ftrack_connect.application.appendPath(
            hiero_plugin_path, 'HIERO_PLUGIN_PATH', environment
        )

        return environment


def register(session, **kw):
    '''Register hooks for ftrack connect legacy plugins.'''

    logger = logging.getLogger(
        'ftrack_plugin:ftrack_connect_hiero_hook.register'
    )

    '''Register plugin. Called when used as an plugin.'''
    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an old or incompatible API and
    # return without doing anything.
    if not isinstance(session, ftrack_api.session.Session):
        return


    applicationStore = ApplicationStore()

    launcher = ApplicationLauncher(applicationStore)

    # Create action and register to respond to discover and launch events.
    action = LaunchAction(applicationStore, launcher, session)
    action.register()