from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ldp_core.models import Activity, LeadershipAward, Person, School


class ActivitySearchTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            username='search-admin', password='test-password', role='ADMIN'
        )
        self.viewer = user_model.objects.create_user(
            username='search-viewer', password='test-password', role='VIEWER'
        )
        self.other_viewer = user_model.objects.create_user(
            username='other-viewer', password='test-password', role='VIEWER'
        )
        self.school = School.objects.create(name='North Valley Academy')
        self.other_school = School.objects.create(name='South Ridge School')
        self.person = Person.objects.create(user=self.viewer, school=self.school)
        Person.objects.create(user=self.other_viewer, school=self.other_school)
        self.alpha = Activity.objects.create(
            name='Leadership Summit', date=date(2026, 5, 1),
            description='Communication and teamwork workshop', school=self.school,
        )
        self.beta = Activity.objects.create(
            name='Science Camp', date=date(2026, 6, 1),
            description='Outdoor research program', school=self.school,
        )
        self.hidden = Activity.objects.create(
            name='Private Leadership Forum', date=date(2026, 7, 1),
            description='Restricted event', school=self.other_school,
        )

    def test_list_search_matches_name_school_and_description(self):
        self.client.force_login(self.admin)
        url = reverse('ldp_core:activity_list')
        for query, expected in (
            ('summit', self.alpha),
            ('north valley', self.beta),
            ('TEAMWORK', self.alpha),
        ):
            with self.subTest(query=query):
                response = self.client.get(url, {'q': f'  {query}  '})
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected, response.context['activities'])
                self.assertEqual(response.context['search_query'], query)

    def test_live_search_respects_user_visibility(self):
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse('ldp_core:activity_live_search'), {'q': 'leadership'}
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual([item['label'] for item in payload['suggestions']], ['Leadership Summit'])
        self.assertNotContains(response, self.hidden.name)

    def test_live_search_requires_authentication(self):
        response = self.client.get(reverse('ldp_core:activity_live_search'), {'q': 'summit'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_live_search_limits_suggestions_and_returns_rendered_results(self):
        for index in range(10):
            Activity.objects.create(
                name=f'Leadership Session {index:02d}',
                date=date(2026, 8, 1),
                school=self.school,
            )
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('ldp_core:activity_live_search'),
            {'q': 'leadership', 'sort': 'name', 'dir': 'asc'},
        )
        payload = response.json()
        self.assertEqual(len(payload['suggestions']), 8)
        self.assertIn('Leadership Session 00', payload['html'])
        self.assertIn('data-activity-results-card', payload['html'])

    def test_short_query_filters_results_without_suggestions(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('ldp_core:activity_live_search'), {'q': 's'})
        payload = response.json()
        self.assertEqual(payload['suggestions'], [])
        self.assertGreaterEqual(payload['count'], 1)

    def test_special_characters_are_safely_encoded_in_pagination(self):
        for index in range(55):
            Activity.objects.create(
                name=f'R&D Session {index:02d}',
                date=date(2026, 9, 1),
                school=self.school,
            )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('ldp_core:activity_list'), {'q': 'R&D'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'q=R%26D')

    def test_primary_directory_pages_expose_live_search(self):
        self.client.force_login(self.admin)
        for route in ('activity_list', 'person_list', 'school_list', 'award_list'):
            with self.subTest(route=route):
                response = self.client.get(reverse(f'ldp_core:{route}'))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-live-list')
                self.assertContains(response, 'data-live-list-input')

    def test_activity_form_exposes_participant_multiselect_autocomplete(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('ldp_core:activity_update', args=[self.alpha.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-local-multiselect')
        self.assertContains(response, 'data-local-multiselect-input')
        self.assertContains(response, 'role="combobox"')
        self.assertContains(response, 'aria-multiselectable="true"')
        self.assertContains(response, f'data-participant-id="{self.person.pk}"')
        self.assertContains(response, self.viewer.username)

    def test_awards_fail_closed_without_authorized_school(self):
        award = LeadershipAward.objects.create(
            recipient=self.person,
            award_title='Visible only to authorized school',
            award_level=LeadershipAward.AwardLevel.SCHOOL,
            year_awarded='2026',
            school=self.school,
        )
        user_model = get_user_model()
        schoolless = user_model.objects.create_user(
            username='schoolless-viewer', password='test-password', role='VIEWER'
        )
        self.client.force_login(schoolless)
        response = self.client.get(reverse('ldp_core:award_list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, award.award_title)
