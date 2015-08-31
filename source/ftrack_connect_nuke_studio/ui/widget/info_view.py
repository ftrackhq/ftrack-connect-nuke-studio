# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import urlparse

import hiero.core

import ftrack_connect.ui.widget.web_view

import ftrack


class InfoView(
    ftrack_connect.ui.widget.web_view.WebView
):
    '''Display information about selected entity.'''

    _identifier = 'com.ftrack.information_panel'
    _display_name = 'Info'

    def __init__(self, parent=None, url=None):
        '''Initialise InvfoView.'''
        super(InfoView, self).__init__(parent, url)

        hiero.core.events.registerInterest(
            'kSelectionChanged', self.on_selection_changed
        )

        self.setWindowTitle(self._display_name)
        self.setObjectName(self._identifier)

    @classmethod
    def get_identifier(self):
        '''Return identifier for widget.'''
        return self._identifier

    @classmethod
    def get_display_name(self):
        '''Return dsiplay name for widget.'''
        return self._display_name

    def set_entity(self, entity):
        '''Display information about specific *entity*.'''
        if entity is None:
            return

        if isinstance(entity, ftrack.Component):
            entity = entity.getVersion()

        if not self.get_url():
            # Load initial page using url retrieved from entity.

            # TODO: Some types of entities don't have this yet, eg
            # assetversions. Add some checking here if it's not going to be
            # available from all entities.
            if hasattr(entity, 'getWebWidgetUrl'):
                url = entity.getWebWidgetUrl(name='info', theme='tf')

                self.set_url(url)

        else:
            # Send javascript to currently loaded page to update view.
            entityId = entity.getId()

            # NOTE: get('entityType') not supported on assetversions so
            # using private _type attribute.
            entityType = entity._type

            javascript = (
                'FT.WebMediator.setEntity({{'
                '   entityId: "{0}",'
                '   entityType: "{1}"'
                '}})'
                .format(entityId, entityType)
            )
            self._webView.page().mainFrame().evaluateJavaScript(javascript)

    def on_selection_changed(self, event):
        '''Handle selection changed events.'''
        selection = event.sender.selection()
        if len(selection) != 1:
            return

        item = selection[0]
        if not isinstance(item, hiero.core.TrackItem):
            return

        identifier = item.source().entityReference()

        if 'ftrack://' not in identifier:
            return

        url = urlparse.urlparse(identifier)
        query = urlparse.parse_qs(url.query)
        entity_type = query.get('entityType')[0]

        identifier = url.netloc

        entity = None
        try:
            if entity_type == 'component':
                entity = ftrack.Component(identifier)

            elif entity_type == 'asset_version':
                entity = ftrack.AssetVersion(identifier)

            elif entity_type == 'asset':
                entity = ftrack.Asset(identifier)

            elif entity_type == 'show':
                entity = ftrack.Project(identifier)

            elif entity_type == 'task':
                entity = ftrack.Task(identifier)

        except Exception:
            pass

        self.set_entity(entity)