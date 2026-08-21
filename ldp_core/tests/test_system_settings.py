import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from ldp_core.models import Person, School, SystemSettings, User
from ldp_core.views import _profile_field_changes


class SystemSettingsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin-settings', password='secret', role=User.Role.ADMIN)
        self.other_admin = User.objects.create_user(username='other-admin', password='secret', role=User.Role.ADMIN)
        self.viewer = User.objects.create_user(username='settings-viewer', password='secret', role=User.Role.VIEWER)

    def test_admin_settings_are_persistent_and_global(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('ldp_core:settings'), {
            'allow_export': 'on',
            'school_sync_enabled': 'on',
            'user_sync_enabled': 'on',
            'activity_sync_enabled': 'on',
            'award_sync_enabled': 'on',
        })
        self.assertRedirects(response, reverse('ldp_core:settings'), fetch_redirect_response=False)
        configuration = SystemSettings.objects.get(pk=1)
        self.assertFalse(configuration.allow_import)
        self.assertEqual(configuration.updated_by, self.admin)

        self.client.force_login(self.other_admin)
        self.assertFalse(SystemSettings.objects.get(pk=1).allow_import)

    def test_non_admin_cannot_open_settings(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('ldp_core:settings'))
        self.assertEqual(response.status_code, 302)

    def test_disabled_import_rejects_direct_upload(self):
        SystemSettings.objects.create(pk=1, allow_import=False)
        self.client.force_login(self.admin)
        upload = SimpleUploadedFile('import.xlsx', b'not-used')
        response = self.client.post(reverse('ldp_core:bulk_import_dashboard'), {'workbook': upload})
        self.assertRedirects(response, reverse('ldp_core:bulk_import_dashboard'), fetch_redirect_response=False)
        self.assertEqual(self.admin.import_jobs.count(), 0)

    def test_old_json_import_route_cannot_mutate_records(self):
        self.client.force_login(self.admin)
        payload = SimpleUploadedFile(
            'schools.json', json.dumps([{'name': 'Unsafe School'}]).encode(),
            content_type='application/json',
        )
        response = self.client.post(reverse('ldp_core:import_data', args=['schools']), {'import_file': payload})
        self.assertRedirects(response, reverse('ldp_core:bulk_import_dashboard'), fetch_redirect_response=False)
        self.assertFalse(School.objects.filter(name='Unsafe School').exists())

    def test_export_uses_versioned_envelope_and_stable_identifier(self):
        School.objects.create(name='Stable School', school_id='SCH-STABLE')
        self.client.force_login(self.admin)
        response = self.client.get(reverse('ldp_core:export_data', args=['schools']))
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload['schema'], 'ldp-data-interchange')
        self.assertEqual(payload['version'], 1)
        self.assertEqual(payload['records'][0]['school_id'], 'SCH-STABLE')
        self.assertNotIn('id', payload['records'][0])

    def test_entity_export_setting_is_enforced(self):
        SystemSettings.objects.create(pk=1, school_sync_enabled=False)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('ldp_core:export_data', args=['schools']))
        self.assertRedirects(response, reverse('ldp_core:bulk_import_dashboard'), fetch_redirect_response=False)

    def test_legacy_migration_requires_post_and_entities(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('ldp_core:legacy_migration')).status_code, 405)
        payload = SimpleUploadedFile('legacy.json', b'{"schools": []}', content_type='application/json')
        response = self.client.post(reverse('ldp_core:legacy_migration'), {
            'migration_file': payload,
            'migration_mode': 'preview',
            'conflict_strategy': 'upsert',
            'field_mapping': '{}',
        })
        self.assertRedirects(response, reverse('ldp_core:bulk_import_dashboard'), fetch_redirect_response=False)
        self.assertNotIn('migration_report', self.client.session)


class ChangeManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='change-admin', password='secret', role=User.Role.ADMIN)
        user = User.objects.create_user(
            username='pending-user', first_name='Current', last_name='Name',
            email='current@example.com', password='secret',
        )
        Person.objects.create(
            user=user,
            contact_number='09170000000',
            address='Same address',
            student_id='OLD-1',
            pending_changes={
                'first_name': 'Current',
                'last_name': 'Updated',
                'email': 'current@example.com',
                'contact_number': '09170000000',
                'address': 'Same address',
                'student_id': 'NEW-2',
            },
            is_pending_approval=True,
        )

    def test_only_actual_changes_are_prepared_for_display(self):
        person = Person.objects.select_related('user').get(user__username='pending-user')
        changed_fields = _profile_field_changes(person)
        self.assertEqual(
            [change['label'] for change in changed_fields],
            ['Last name', 'Student / Scholar ID'],
        )
