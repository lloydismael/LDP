import re
from django import forms
from django.db import transaction
from .models import Person, User, Activity, School, LeadershipAward


class LeadershipAwardForm(forms.ModelForm):
    class Meta:
        model = LeadershipAward
        fields = ['recipient', 'award_title', 'award_level', 'year_awarded', 'awarding_body', 'description', 'certificate', 'school']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.principal_school = kwargs.pop('principal_school', None)
        super().__init__(*args, **kwargs)
        if self.principal_school:
            self.fields['recipient'].queryset = Person.objects.filter(
                school=self.principal_school
            ).select_related('user').order_by('user__last_name', 'user__first_name')
            self.fields['school'].queryset = School.objects.filter(pk=self.principal_school.pk)
            self.fields['school'].initial = self.principal_school
            self.fields['school'].empty_label = None
            self.fields['school'].disabled = True
        else:
            self.fields['recipient'].queryset = Person.objects.all().select_related('user').order_by('user__last_name')
            self.fields['school'].queryset = School.objects.all()


class ActivityForm(forms.ModelForm):
    participants = forms.ModelMultipleChoiceField(
        queryset=Person.objects.none(),
        required=False,
        label='Participants',
        widget=forms.SelectMultiple(attrs={'size': '8'}),
    )

    class Meta:
        model = Activity
        fields = ['name', 'date', 'description', 'banner', 'school']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.principal_school = kwargs.pop('principal_school', None)
        super().__init__(*args, **kwargs)
        if self.principal_school:
            self.fields['participants'].queryset = Person.objects.filter(
                school=self.principal_school
            ).select_related('user').order_by('user__last_name', 'user__first_name')
            # Lock school to principal's school
            self.fields['school'].queryset = School.objects.filter(pk=self.principal_school.pk)
            self.fields['school'].empty_label = None
        else:
            self.fields['participants'].queryset = Person.objects.all().select_related('user').order_by('user__last_name')
        # Pre-select existing participants when editing
        if self.instance and self.instance.pk:
            self.fields['participants'].initial = self.instance.participants.all()

    def save(self, commit=True):
        activity = super().save(commit=commit)
        if commit:
            participants = self.cleaned_data.get('participants', [])
            activity.participants.set(participants)
        return activity

class UserProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False, label='Email Address')

    class Meta:
        model = Person
        fields = [
            'first_name', 'last_name', 'email', 'profile_photo', 'banner',
            'contact_number', 'address', 'bio',
            'student_id', 'year_level', 'course_program',
            'section', 'scholarship_type', 'year_started', 'year_ended',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        person = super().save(commit=False)
        pending = {
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'email': self.cleaned_data.get('email', ''),
            'contact_number': self.cleaned_data['contact_number'],
            'address': self.cleaned_data['address'],
            'bio': self.cleaned_data['bio'],
            'student_id': self.cleaned_data.get('student_id', ''),
            'year_level': self.cleaned_data.get('year_level', ''),
            'course_program': self.cleaned_data.get('course_program', ''),
            'section': self.cleaned_data.get('section', ''),
            'scholarship_type': self.cleaned_data.get('scholarship_type', ''),
            'year_started': self.cleaned_data.get('year_started', ''),
            'year_ended': self.cleaned_data.get('year_ended', ''),
        }

        if person.pk:
            db_person = Person.objects.get(pk=person.pk)
            person.contact_number = db_person.contact_number
            person.address = db_person.address
            person.bio = db_person.bio
            person.student_id = db_person.student_id
            person.year_level = db_person.year_level
            person.course_program = db_person.course_program
            person.section = db_person.section
            person.scholarship_type = db_person.scholarship_type
            person.year_started = db_person.year_started
            person.year_ended = db_person.year_ended

        person.pending_changes = pending
        person.is_pending_approval = True

        if commit:
            person.save()
        return person

PHILIPPINE_REGIONS = [
    ('NCR', 'National Capital Region (NCR)'),
    ('CAR', 'Cordillera Administrative Region (CAR)'),
    ('Region I', 'Ilocos Region (Region I)'),
    ('Region II', 'Cagayan Valley (Region II)'),
    ('Region III', 'Central Luzon (Region III)'),
    ('Region IV-A', 'CALABARZON (Region IV-A)'),
    ('Region IV-B', 'MIMAROPA (Region IV-B)'),
    ('Region V', 'Bicol Region (Region V)'),
    ('Region VI', 'Western Visayas (Region VI)'),
    ('Region VII', 'Central Visayas (Region VII)'),
    ('Region VIII', 'Eastern Visayas (Region VIII)'),
    ('Region IX', 'Zamboanga Peninsula (Region IX)'),
    ('Region X', 'Northern Mindanao (Region X)'),
    ('Region XI', 'Davao Region (Region XI)'),
    ('Region XII', 'SOCCSKSARGEN (Region XII)'),
    ('Region XIII', 'Caraga (Region XIII)'),
    ('BARMM', 'Bangsamoro Autonomous Region in Muslim Mindanao (BARMM)'),
]

# A dictionary mapping regions to their provinces
REGION_PROVINCES = {
    'NCR': ['Metro Manila'],
    'CAR': ['Abra', 'Apayao', 'Benguet', 'Ifugao', 'Kalinga', 'Mountain Province'],
    'Region I': ['Ilocos Norte', 'Ilocos Sur', 'La Union', 'Pangasinan'],
    'Region II': ['Batanes', 'Cagayan', 'Isabela', 'Nueva Vizcaya', 'Quirino'],
    'Region III': ['Aurora', 'Bataan', 'Bulacan', 'Nueva Ecija', 'Pampanga', 'Tarlac', 'Zambales'],
    'Region IV-A': ['Batangas', 'Cavite', 'Laguna', 'Quezon', 'Rizal'],
    'Region IV-B': ['Marinduque', 'Occidental Mindoro', 'Oriental Mindoro', 'Palawan', 'Romblon'],
    'Region V': ['Albay', 'Camarines Norte', 'Camarines Sur', 'Catanduanes', 'Masbate', 'Sorsogon'],
    'Region VI': ['Aklan', 'Antique', 'Capiz', 'Guimaras', 'Iloilo', 'Negros Occidental'],
    'Region VII': ['Bohol', 'Cebu', 'Negros Oriental', 'Siquijor'],
    'Region VIII': ['Biliran', 'Eastern Samar', 'Leyte', 'Northern Samar', 'Samar', 'Southern Leyte'],
    'Region IX': ['Zamboanga del Norte', 'Zamboanga del Sur', 'Zamboanga Sibugay'],
    'Region X': ['Bukidnon', 'Camiguin', 'Lanao del Norte', 'Misamis Occidental', 'Misamis Oriental'],
    'Region XI': ['Davao de Oro', 'Davao del Norte', 'Davao del Sur', 'Davao Occidental', 'Davao Oriental'],
    'Region XII': ['Cotabato', 'Sarangani', 'South Cotabato', 'Sultan Kudarat'],
    'Region XIII': ['Agusan del Norte', 'Agusan del Sur', 'Dinagat Islands', 'Surigao del Norte', 'Surigao del Sur'],
    'BARMM': ['Basilan', 'Lanao del Sur', 'Maguindanao del Norte', 'Maguindanao del Sur', 'Sulu', 'Tawi-Tawi']
}

class SchoolForm(forms.ModelForm):
    region = forms.ChoiceField(choices=[('', '-- Select Region --')] + PHILIPPINE_REGIONS, required=False)
    school_type = forms.ChoiceField(
        choices=[('', '-- Select Type --')] + [(t.value, t.label) for t in School.SchoolType],
        required=False,
        label='School Type'
    )

    class Meta:
        model = School
        fields = [
            'name', 'school_id', 'school_type', 'category',
            'address', 'location', 'district', 'division', 'province', 'region',
            'email', 'phone', 'website',
            'founded_year', 'is_active', 'principal',
            'logo', 'banner',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            user_ids = Person.objects.filter(school=self.instance, type=Person.Type.PRINCIPAL).values_list('user_id', flat=True)
            self.fields['principal'].queryset = User.objects.filter(id__in=user_ids, role=User.Role.PRINCIPAL)
        else:
            self.fields['principal'].queryset = User.objects.none()
            self.fields['principal'].help_text = "Save the school first, then assign a Principal."

class PersonCreateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)

    class Meta:
        model = Person
        fields = ['first_name', 'last_name', 'type', 'school']

    def __init__(self, *args, **kwargs):
        self.principal_school = kwargs.pop('principal_school', None)
        super().__init__(*args, **kwargs)
        if self.principal_school:
            allowed = [Person.Type.STUDENT, Person.Type.SCHOLAR, Person.Type.COLLEGE, Person.Type.PROFESSIONAL]
            self.fields['type'].choices = [(t.value, t.label) for t in allowed]
            self.fields['school'].queryset = School.objects.filter(pk=self.principal_school.pk)
            self.fields['school'].initial = self.principal_school
            self.fields['school'].empty_label = None
            self.fields['school'].disabled = True

    def save(self, commit=True):
        person = super().save(commit=False)
        # If school is disabled (principal use), restore from principal_school
        if self.principal_school and not person.school_id:
            person.school = self.principal_school
        first_name = self.cleaned_data['first_name'].strip()
        last_name = self.cleaned_data['last_name'].strip()
        
        # Generate username: Firstname + First capital letter of their Surname
        base_username = f"{first_name}{last_name[0].upper()}".replace(" ", "")
        username = base_username
        
        # Handle potential duplicates
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        with transaction.atomic():
            # Determine correct User Role based on Person Type
            role_map = {
                Person.Type.PRINCIPAL: User.Role.PRINCIPAL,
                Person.Type.SCHOLAR: User.Role.SCHOLAR,
                Person.Type.PROFESSIONAL: User.Role.PROFESSIONAL,
                Person.Type.STUDENT: User.Role.VIEWER,
            }
            assigned_role = role_map.get(person.type, User.Role.VIEWER)

            # Create the auto-generated User
            user = User.objects.create_user(
                username=username,
                password='@Password123',
                first_name=first_name,
                last_name=last_name,
                role=assigned_role,
                must_change_password=True
            )
            person.user = user
            if commit:
                person.save()
        return person

class PersonUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False, label='Email Address')

    class Meta:
        model = Person
        fields = [
            'first_name', 'last_name', 'email',
            'type', 'school', 'activities',
            'profile_photo', 'banner', 'contact_number', 'address', 'bio',
            'student_id', 'year_level', 'course_program',
            'section', 'scholarship_type', 'year_started', 'year_ended',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        person = super().save(commit=False)
        if person.user:
            person.user.first_name = self.cleaned_data['first_name']
            person.user.last_name = self.cleaned_data['last_name']
            if self.cleaned_data.get('email'):
                person.user.email = self.cleaned_data['email']

            # Sync user role if person type changed
            role_map = {
                Person.Type.PRINCIPAL: User.Role.PRINCIPAL,
                Person.Type.SCHOLAR: User.Role.SCHOLAR,
                Person.Type.PROFESSIONAL: User.Role.PROFESSIONAL,
                Person.Type.STUDENT: User.Role.VIEWER,
            }
            person.user.role = role_map.get(person.type, User.Role.VIEWER)

            if commit:
                person.user.save()
        if commit:
            person.save()
            self.save_m2m()
        return person