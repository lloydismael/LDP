from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class FileData(models.Model):
    """Stores uploaded binary files in the PostgreSQL database.
    Used by django-db-file-storage as the storage backend model."""
    content = models.TextField()
    mimetype = models.CharField(max_length=255)
    filename = models.CharField(max_length=255)

    class Meta:
        app_label = 'ldp_core'

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        ENCODER = 'ENCODER', 'Encoder'
        VIEWER = 'VIEWER', 'Viewer'
        PRINCIPAL = 'PRINCIPAL', 'Principal'
        SCHOLAR = 'SCHOLAR', 'Scholar'
        PROFESSIONAL = 'PROFESSIONAL', 'Professional'
    
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.VIEWER)
    must_change_password = models.BooleanField(default=True)

class School(models.Model):
    class SchoolType(models.TextChoices):
        ELEMENTARY = 'ELEMENTARY', 'Elementary School'
        SECONDARY = 'SECONDARY', 'Secondary / Junior High School'
        SENIOR_HIGH = 'SENIOR_HIGH', 'Senior High School'
        INTEGRATED = 'INTEGRATED', 'Integrated School (K–12)'
        COLLEGE = 'COLLEGE', 'College / University'
        TECH_VOC = 'TECH_VOC', 'Technical-Vocational Institute'
        SPECIAL = 'SPECIAL', 'Special Education School'
        OTHER = 'OTHER', 'Other'

    # Core Identification
    name = models.CharField(max_length=255, verbose_name='School Name')
    school_id = models.CharField(max_length=100, blank=True, verbose_name='School ID / EMiS No.')
    school_type = models.CharField(max_length=50, choices=SchoolType.choices, blank=True, verbose_name='School Type')
    category = models.CharField(max_length=100, blank=True, verbose_name='Category / Classification')

    # Location
    address = models.TextField(blank=True, verbose_name='Street Address')
    location = models.CharField(max_length=255, default='Philippines', verbose_name='City / Municipality')
    district = models.CharField(max_length=100, blank=True, verbose_name='District')
    division = models.CharField(max_length=100, blank=True, verbose_name='Division / Department')
    province = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)

    # Contact
    email = models.EmailField(blank=True, verbose_name='School Email')
    phone = models.CharField(max_length=50, blank=True, verbose_name='Contact Number')
    website = models.URLField(blank=True, verbose_name='Website URL')

    # Media
    logo = models.ImageField(upload_to='ldp_core.filedata/content/filename/mimetype', blank=True, null=True, verbose_name='School Logo')
    banner = models.ImageField(upload_to='ldp_core.filedata/content/filename/mimetype', blank=True, null=True, verbose_name='School Banner')

    # Other Details
    founded_year = models.CharField(max_length=10, blank=True, verbose_name='Year Founded')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    principal = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_schools', limit_choices_to={'role': User.Role.PRINCIPAL})

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not is_new:
            try:
                old = School.objects.get(pk=self.pk)
                old_principal_id = old.principal_id
            except School.DoesNotExist:
                old_principal_id = None
        else:
            old_principal_id = None

        super().save(*args, **kwargs)

        # Record history when principal changes
        if is_new:
            if self.principal_id:
                SchoolPrincipalHistory.objects.create(
                    school=self,
                    principal=self.principal,
                    principal_name=self.principal.get_full_name() or self.principal.username,
                    assigned_at=timezone.now().date(),
                )
        elif old_principal_id != self.principal_id:
            # Close the current open record
            SchoolPrincipalHistory.objects.filter(
                school=self, removed_at__isnull=True
            ).update(removed_at=timezone.now().date())
            # Open a new record if a principal is being assigned
            if self.principal_id:
                SchoolPrincipalHistory.objects.create(
                    school=self,
                    principal=self.principal,
                    principal_name=self.principal.get_full_name() or self.principal.username,
                    assigned_at=timezone.now().date(),
                )

    def __str__(self):
        return self.name


class SchoolPrincipalHistory(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='principal_history')
    principal = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='principal_history')
    principal_name = models.CharField(max_length=255, blank=True, verbose_name='Principal Name')
    assigned_at = models.DateField(verbose_name='Date Assigned')
    removed_at = models.DateField(null=True, blank=True, verbose_name='Date Removed')
    notes = models.TextField(blank=True, verbose_name='Notes')

    class Meta:
        ordering = ['-assigned_at']
        verbose_name = 'Principal Assignment History'
        verbose_name_plural = 'Principal Assignment Histories'

    def __str__(self):
        return f"{self.principal_name} @ {self.school} ({self.assigned_at})"


class Activity(models.Model):
    name = models.CharField(max_length=255)
    date = models.DateField()
    description = models.TextField(blank=True)
    banner = models.ImageField(upload_to='ldp_core.filedata/content/filename/mimetype', blank=True, null=True, verbose_name='Activity Banner')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_activities')

    def __str__(self):
        return self.name

class LeadershipAward(models.Model):
    class AwardLevel(models.TextChoices):
        SCHOOL = 'SCHOOL', 'School Level'
        DISTRICT = 'DISTRICT', 'District Level'
        DIVISION = 'DIVISION', 'Division Level'
        REGIONAL = 'REGIONAL', 'Regional Level'
        NATIONAL = 'NATIONAL', 'National Level'

    recipient = models.ForeignKey('Person', on_delete=models.CASCADE, related_name='leadership_awards')
    award_title = models.CharField(max_length=255, verbose_name='Award Title')
    award_level = models.CharField(max_length=50, choices=AwardLevel.choices, default=AwardLevel.SCHOOL, verbose_name='Award Level')
    year_awarded = models.CharField(max_length=10, verbose_name='Year Awarded')
    awarding_body = models.CharField(max_length=255, blank=True, verbose_name='Awarding Body / Organization')
    description = models.TextField(blank=True, verbose_name='Description / Notes')
    certificate = models.ImageField(upload_to='ldp_core.filedata/content/filename/mimetype', blank=True, null=True, verbose_name='Certificate / Photo')
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True, related_name='awards', verbose_name='School')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year_awarded', 'award_title']

    def __str__(self):
        return f"{self.award_title} — {self.recipient}"


class Person(models.Model):
    class Type(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        SCHOLAR = 'SCHOLAR', 'Scholar'
        COLLEGE = 'COLLEGE', 'College'
        PROFESSIONAL = 'PROFESSIONAL', 'Professional'
        PRINCIPAL = 'PRINCIPAL', 'Principal'
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    type = models.CharField(max_length=50, choices=Type.choices, default=Type.STUDENT)
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, related_name='people')
    activities = models.ManyToManyField(Activity, blank=True, related_name='participants')
    
    # Profile Extensions
    profile_photo = models.ImageField(upload_to='ldp_core.filedata/content/filename/mimetype', blank=True, null=True)
    banner = models.ImageField(upload_to='ldp_core.filedata/content/filename/mimetype', blank=True, null=True, verbose_name='Profile Banner')
    contact_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    bio = models.TextField(blank=True)
    # School / Academic Details
    student_id = models.CharField(max_length=50, blank=True, verbose_name='Student / Scholar ID')
    year_level = models.CharField(max_length=50, blank=True, verbose_name='Year Level / Grade')
    course_program = models.CharField(max_length=255, blank=True, verbose_name='Course / Program')
    section = models.CharField(max_length=50, blank=True, verbose_name='Section / Batch')
    scholarship_type = models.CharField(max_length=255, blank=True, verbose_name='Scholarship Type / Award')
    year_started = models.CharField(max_length=10, blank=True, verbose_name='Year Started')
    year_ended = models.CharField(max_length=10, blank=True, verbose_name='Year Ended / Graduated')
    pending_changes = models.JSONField(blank=True, null=True)
    is_pending_approval = models.BooleanField(default=False)
    
    def __str__(self):
        if self.user:
            return self.user.get_full_name()
        return f"Person {self.id}"


class ProfessionalJob(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = 'FULL_TIME', 'Full-time'
        PART_TIME = 'PART_TIME', 'Part-time'
        CONTRACT = 'CONTRACT', 'Contract'
        FREELANCE = 'FREELANCE', 'Freelance / Self-employed'
        INTERNSHIP = 'INTERNSHIP', 'Internship / OJT'
        VOLUNTEER = 'VOLUNTEER', 'Volunteer'
        OTHER = 'OTHER', 'Other'

    person = models.ForeignKey(
        'Person', on_delete=models.CASCADE, related_name='jobs'
    )
    job_title = models.CharField(max_length=255, verbose_name='Job Title / Position')
    employer = models.CharField(max_length=255, verbose_name='Employer / Company')
    employment_type = models.CharField(
        max_length=20, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME,
        verbose_name='Employment Type'
    )
    location = models.CharField(max_length=255, blank=True, verbose_name='Location / Office')
    start_date = models.DateField(verbose_name='Start Date')
    end_date = models.DateField(null=True, blank=True, verbose_name='End Date')
    is_current = models.BooleanField(default=False, verbose_name='Currently Working Here')
    description = models.TextField(blank=True, verbose_name='Responsibilities / Notes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_current', '-start_date']
        verbose_name = 'Professional Job'
        verbose_name_plural = 'Professional Jobs'

    def __str__(self):
        return f"{self.job_title} at {self.employer}"


class PersonTransferHistory(models.Model):
    """Tracks every school transfer made for a person."""
    class Reason(models.TextChoices):
        PROMOTION = 'PROMOTION', 'Promotion / Reassignment'
        RELOCATION = 'RELOCATION', 'Family Relocation'
        COMPLETION = 'COMPLETION', 'Course Completion / Graduation'
        SCHOLARSHIP = 'SCHOLARSHIP', 'Scholarship Transfer'
        ADMINISTRATIVE = 'ADMINISTRATIVE', 'Administrative Order'
        OTHER = 'OTHER', 'Other'

    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name='transfer_history'
    )
    from_school = models.ForeignKey(
        School, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfers_out', verbose_name='From School'
    )
    to_school = models.ForeignKey(
        School, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfers_in', verbose_name='To School'
    )
    transfer_date = models.DateField(verbose_name='Transfer Date')
    effective_date = models.DateField(null=True, blank=True, verbose_name='Effective Date')
    reason = models.CharField(
        max_length=50, choices=Reason.choices, default=Reason.OTHER,
        verbose_name='Reason for Transfer'
    )
    notes = models.TextField(blank=True, verbose_name='Notes / Remarks')
    processed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='processed_transfers', verbose_name='Processed By'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transfer_date']
        verbose_name = 'Transfer History'
        verbose_name_plural = 'Transfer Histories'

    def __str__(self):
        return (
            f"{self.person} | {self.from_school} → {self.to_school} "
            f"({self.transfer_date})"
        )
