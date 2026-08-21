from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from ldp_core.forms import PersonCreateForm
from ldp_core.models import Person, School
from ldp_core.views import PersonCreateView


class PersonCreateFormTests(TestCase):
    def setUp(self):
        self.active_school = School.objects.create(name='Active Academy')
        self.inactive_school = School.objects.create(name='Closed Academy', is_active=False)

    def test_form_provides_guidance_and_only_active_schools(self):
        form = PersonCreateForm()

        self.assertIn('given name', form.fields['first_name'].help_text)
        self.assertIn('account access', form.fields['type'].help_text)
        self.assertQuerySetEqual(
            form.fields['school'].queryset,
            [self.active_school],
        )

    def test_whitespace_only_names_are_rejected(self):
        form = PersonCreateForm(data={
            'first_name': '   ',
            'last_name': '   ',
            'type': Person.Type.STUDENT,
            'school': self.active_school.pk,
        })

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['first_name'], ['Enter the participant’s first name.'])
        self.assertEqual(form.errors['last_name'], ['Enter the participant’s last name.'])

    def test_names_are_trimmed_before_account_creation(self):
        form = PersonCreateForm(data={
            'first_name': '  Maria  ',
            'last_name': '  Santos  ',
            'type': Person.Type.SCHOLAR,
            'school': self.active_school.pk,
        })

        self.assertTrue(form.is_valid(), form.errors)
        person = form.save()
        self.assertEqual(person.user.first_name, 'Maria')
        self.assertEqual(person.user.last_name, 'Santos')
        self.assertEqual(person.user.username, 'MariaS')
        self.assertEqual(person.user.role, 'SCHOLAR')
        self.assertTrue(person.user.must_change_password)


class PersonCreateViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            username='people-admin', password='test-password', role='ADMIN',
            must_change_password=False,
        )
        self.school = School.objects.create(name='North Valley Academy')
        self.other_school = School.objects.create(name='South Ridge School')
        self.url = reverse('ldp_core:person_create')
        self.factory = RequestFactory()

    def request_for(self, user, method='get', data=None):
        request = getattr(self.factory, method)(self.url, data=data or {})
        request.user = user
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        MessageMiddleware(lambda req: None).process_request(request)
        return request

    def test_admin_form_renders_guidance_and_accessibility_hooks(self):
        response = PersonCreateView.as_view()(self.request_for(self.admin))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.template_name, ['ldp_core/person_form.html'])
        self.assertIn('given name', response.context_data['form'].fields['first_name'].help_text)
        self.assertIsNone(response.context_data['principal_school'])

    def test_success_message_includes_generated_username(self):
        request = self.request_for(self.admin, 'post', {
            'first_name': 'Juan',
            'last_name': 'Cruz',
            'type': Person.Type.STUDENT,
            'school': self.school.pk,
        })
        response = PersonCreateView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        message_text = ' '.join(str(message) for message in get_messages(request))
        self.assertIn('Participant created successfully.', message_text)
        self.assertIn('JuanC', message_text)
        created = Person.objects.get(user__username='JuanC')
        self.assertEqual(created.school, self.school)

    def test_schoolless_principal_is_denied(self):
        principal = get_user_model().objects.create_user(
            username='schoolless-principal', password='test-password', role='PRINCIPAL',
            must_change_password=False,
        )
        with self.assertRaisesMessage(PermissionDenied, 'A school assignment is required'):
            PersonCreateView.as_view()(self.request_for(principal))

    def test_principal_school_and_types_are_locked(self):
        principal = get_user_model().objects.create_user(
            username='assigned-principal', password='test-password', role='PRINCIPAL',
            must_change_password=False,
        )
        Person.objects.create(
            user=principal,
            type=Person.Type.PRINCIPAL,
            school=self.school,
        )
        response = PersonCreateView.as_view()(self.request_for(principal))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['principal_school'], self.school)
        choices = {value for value, _label in response.context_data['form'].fields['type'].choices}
        self.assertNotIn(Person.Type.PRINCIPAL, choices)

    def test_principal_cannot_submit_another_school(self):
        principal = get_user_model().objects.create_user(
            username='locked-principal', password='test-password', role='PRINCIPAL',
            must_change_password=False,
        )
        Person.objects.create(
            user=principal,
            type=Person.Type.PRINCIPAL,
            school=self.school,
        )
        request = self.request_for(principal, 'post', {
            'first_name': 'Ana',
            'last_name': 'Reyes',
            'type': Person.Type.STUDENT,
            'school': self.other_school.pk,
        })
        response = PersonCreateView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        created = Person.objects.get(user__username='AnaR')
        self.assertEqual(created.school, self.school)
