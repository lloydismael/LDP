import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from ldp_core.models import Activity, ImportJob, LeadershipAward, Person, School, User
from ldp_core.services.imports import apply_job, create_job, parse_bool, workbook_bytes


class BulkImportServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin', password='secret', role=User.Role.ADMIN
        )

    def populated_workbook(self):
        content = workbook_bytes()
        workbook = load_workbook(io.BytesIO(content))
        workbook['Schools'].append([
            'SCH-001', 'North School', 'SECONDARY', '', '', 'Manila', '', '', '',
            'NCR', '', '', '', '2000', True, 'principal1',
        ])
        workbook['Users'].append([
            'principal1', 'Pat', 'Principal', 'pat@example.com', 'PRINCIPAL', True,
            'PRINCIPAL', 'SCH-001', '', '', '', '', '', '', '', '', '', '',
        ])
        workbook['Users'].append([
            'scholar1', 'Sam', 'Scholar', 'sam@example.com', 'SCHOLAR', True,
            'SCHOLAR', 'SCH-001', '', '', '', 'S-1', 'Grade 12', '', '', '', '2025', '',
        ])
        workbook['Activities'].append([
            'SCH-001', 'Leadership Camp', '2026-08-20', 'Annual camp', True,
        ])
        workbook['ActivityParticipants'].append([
            'SCH-001', 'Leadership Camp', '2026-08-20', 'scholar1',
        ])
        workbook['LeadershipAwards'].append([
            'scholar1', 'Youth Leader', 'DIVISION', '2026', 'Schools Division', '', 'SCH-001',
        ])
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()

    def test_parse_bool_rejects_ambiguous_values(self):
        self.assertTrue(parse_bool('yes'))
        self.assertFalse(parse_bool('false'))
        with self.assertRaises(ValueError):
            parse_bool('sometimes')

    def test_preview_then_apply_complete_workbook(self):
        content = self.populated_workbook()
        upload = SimpleUploadedFile('import.xlsx', content)
        job = create_job(upload, self.admin)

        self.assertEqual(job.status, ImportJob.Status.READY)
        self.assertEqual(job.error_count, 0)
        self.assertEqual(job.create_count, 6)
        self.assertEqual(School.objects.count(), 0)

        apply_job(job)
        job.refresh_from_db()
        school = School.objects.get(school_id='SCH-001')
        scholar = Person.objects.get(user__username='scholar1')
        activity = Activity.objects.get(name='Leadership Camp')

        self.assertEqual(job.status, ImportJob.Status.APPLIED)
        self.assertEqual(school.principal.username, 'principal1')
        self.assertTrue(User.objects.get(username='scholar1').has_usable_password() is False)
        self.assertTrue(activity.participants.filter(pk=scholar.pk).exists())
        self.assertTrue(activity.is_approved)
        self.assertEqual(activity.approved_by, self.admin)
        self.assertTrue(LeadershipAward.objects.filter(recipient=scholar, award_title='Youth Leader').exists())

    def test_invalid_workbook_is_saved_as_invalid_job(self):
        upload = SimpleUploadedFile('broken.xlsx', b'not-an-xlsx')
        job = create_job(upload, self.admin)
        self.assertEqual(job.status, ImportJob.Status.INVALID)
        self.assertIn('not a valid', job.failure_message)


class BulkImportViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='secret', role=User.Role.ADMIN)
        self.viewer = User.objects.create_user(
            username='viewer', password='secret', role=User.Role.VIEWER,
            must_change_password=False,
        )

    def test_admin_can_download_template(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('ldp_core:bulk_import_template'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'PK'))

    def test_non_admin_is_denied_dashboard(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('ldp_core:bulk_import_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('ldp_core:dashboard')))

    def test_apply_requires_post(self):
        job = ImportJob.objects.create(
            uploaded_by=self.admin,
            original_filename='x.xlsx',
            checksum='a' * 64,
            workbook_data=workbook_bytes(),
            status=ImportJob.Status.READY,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('ldp_core:bulk_import_apply', args=[job.pk]))
        self.assertEqual(response.status_code, 405)
