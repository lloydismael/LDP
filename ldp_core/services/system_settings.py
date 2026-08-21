"""Persistent administrator controls for data-management operations."""

from django.db import transaction

from ldp_core.models import SystemSettings


ENTITY_FIELDS = {
    'schools': 'school_sync_enabled',
    'users': 'user_sync_enabled',
    'people': 'user_sync_enabled',
    'activities': 'activity_sync_enabled',
    'awards': 'award_sync_enabled',
}


@transaction.atomic
def get_system_settings():
    """Return the single global settings record, creating it when required."""
    configuration, _ = SystemSettings.objects.select_for_update().get_or_create(pk=1)
    return configuration


def operation_enabled(operation, entity=None, configuration=None):
    configuration = configuration or get_system_settings()
    global_field = 'allow_import' if operation == 'import' else 'allow_export'
    if not getattr(configuration, global_field):
        return False
    entity_field = ENTITY_FIELDS.get((entity or '').lower())
    return not entity_field or getattr(configuration, entity_field)
