from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from .models import School, Person, Activity, LeadershipAward, SchoolPrincipalHistory, PersonTransferHistory, ProfessionalJob, ImportJob
from .forms import PersonCreateForm, PersonUpdateForm, ActivityForm, SchoolForm, UserProfileUpdateForm, LeadershipAwardForm, SchoolPrincipalHistoryForm, PersonTransferForm, ProfessionalJobForm, BulkImportUploadForm, LegacyMigrationForm, SystemSettingsForm, configured_import_limit_mb
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.contrib.auth import get_user_model
import csv
import io
import json
from datetime import date, timedelta

from .services.imports import ImportValidationError, apply_job, create_job, workbook_bytes
from .services.system_settings import get_system_settings, operation_enabled


def _is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role == 'ADMIN')


admin_required = user_passes_test(_is_admin, login_url=reverse_lazy('ldp_core:dashboard'))

@login_required
def dashboard(request):
    user = request.user
    if user.is_superuser or user.role == 'ADMIN':
        schools_count = School.objects.filter(is_active=True).count()
        people_count = Person.objects.count()
        activities_count = Activity.objects.count()
        visible_activities = Activity.objects.all()
    elif hasattr(user, 'person') and user.person and user.person.school:
        schools_count = 1
        people_count = Person.objects.filter(school=user.person.school).count()
        activities_count = Activity.objects.filter(school=user.person.school).count()
        visible_activities = Activity.objects.filter(
            Q(school=user.person.school) | Q(participants=user.person)
        ).distinct()
    else:
        schools_count = 0
        people_count = 0
        activities_count = 0
        visible_activities = Activity.objects.none()

    today = date.today()
    upcoming_activities = list(
        visible_activities.filter(date__gte=today, date__lte=today + timedelta(days=90))
        .select_related('school')
        .annotate(participant_count=Count('participants', distinct=True))
        .order_by('date', 'name')[:6]
    )

    context = {
        'schools_count': schools_count,
        'people_count': people_count,
        'activities_count': activities_count,
        'pending_changes_count': Person.objects.filter(is_pending_approval=True).count() if (user.is_superuser or user.role == 'ADMIN') else 0,
        'upcoming_activities': upcoming_activities,
        'today': today,
    }
    return render(request, 'ldp_core/dashboard.html', context)


class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return _is_admin(self.request.user)


@admin_required
def bulk_import_dashboard(request):
    configuration = get_system_settings()
    if request.method == 'POST':
        if not operation_enabled('import', configuration=configuration):
            messages.error(request, 'Data imports are disabled in System Settings.')
            return redirect('ldp_core:bulk_import_dashboard')
        form = BulkImportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            job = create_job(form.cleaned_data['workbook'], request.user)
            if job.status == ImportJob.Status.READY:
                messages.success(request, 'Workbook preview is ready. Review all changes before applying.')
            else:
                messages.error(request, 'Workbook validation found errors. Review the report below.')
            return redirect('ldp_core:bulk_import_detail', pk=job.pk)
    else:
        form = BulkImportUploadForm()
    jobs = ImportJob.objects.select_related('uploaded_by')[:50]
    return render(request, 'ldp_core/admin_tools/import_dashboard.html', {
        'form': form,
        'jobs': jobs,
        'configuration': configuration,
        'migration_form': LegacyMigrationForm(initial={
            'migration_mode': 'preview',
            'conflict_strategy': 'upsert',
            'entities': [choice[0] for choice in LegacyMigrationForm.ENTITIES],
            'field_mapping': json.dumps(MIGRATION_DEFAULT_MAPPING, indent=2),
        }),
        'migration_report': request.session.get('migration_report'),
        'max_import_mb': configured_import_limit_mb(),
        'school_count': School.objects.count(),
        'user_count': get_user_model().objects.count(),
        'activity_count': Activity.objects.count(),
        'award_count': LeadershipAward.objects.count(),
    })


@admin_required
def bulk_import_template(request):
    if not operation_enabled('import'):
        messages.error(request, 'Data imports are disabled in System Settings.')
        return redirect('ldp_core:bulk_import_dashboard')
    response = HttpResponse(
        workbook_bytes(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="ldp-bulk-import-template-v1.xlsx"'
    return response


@admin_required
def bulk_import_detail(request, pk):
    job = get_object_or_404(ImportJob.objects.select_related('uploaded_by'), pk=pk)
    configuration = get_system_settings()
    rows = job.row_results.all()
    selected_sheet = request.GET.get('sheet', '').strip()
    selected_action = request.GET.get('action', '').strip().upper()
    if selected_sheet:
        rows = rows.filter(sheet_name=selected_sheet)
    if selected_action:
        rows = rows.filter(action=selected_action)
    context = {
        'job': job,
        'rows': rows[:500],
        'sheets': job.row_results.values_list('sheet_name', flat=True).distinct(),
        'selected_sheet': selected_sheet,
        'selected_action': selected_action,
        'configuration': configuration,
    }
    return render(request, 'ldp_core/admin_tools/import_detail.html', context)


@admin_required
def bulk_import_apply(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not operation_enabled('import'):
        messages.error(request, 'Data imports are disabled in System Settings.')
        return redirect('ldp_core:bulk_import_detail', pk=pk)
    job = get_object_or_404(ImportJob, pk=pk)
    try:
        apply_job(job)
    except ImportValidationError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f'Import failed and all domain changes were rolled back: {exc}')
    else:
        messages.success(request, 'Workbook applied successfully.')
    return redirect('ldp_core:bulk_import_detail', pk=job.pk)


@admin_required
def bulk_import_error_report(request, pk):
    job = get_object_or_404(ImportJob, pk=pk)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="import-{job.pk}-report.csv"'
    writer = csv.writer(response)
    writer.writerow(['sheet', 'row', 'external_key', 'action', 'errors', 'changes'])
    for result in job.row_results.all():
        writer.writerow([
            result.sheet_name,
            result.row_number,
            result.external_key,
            result.action,
            ' | '.join(result.errors),
            json.dumps(result.changes, ensure_ascii=False),
        ])
    if job.failure_message and not job.row_results.exists():
        writer.writerow(['Workbook', '', '', 'ERROR', job.failure_message, ''])
    return response


class PrincipalOrAdminMixin(UserPassesTestMixin):
    """Allows Admin/Superuser OR any Principal."""
    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.role in ('ADMIN', 'PRINCIPAL')


class SchoolEditMixin(UserPassesTestMixin):
    """Allows Admin/Superuser OR the Principal assigned to this specific school."""
    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            return True
        if user.role == 'PRINCIPAL':
            school = self.get_object()
            return school.principal == user
        return False

class SchoolListView(LoginRequiredMixin, ListView):
    model = School
    template_name = 'ldp_core/school_list.html'
    context_object_name = 'schools'
    paginate_by = 50

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            qs = School.objects.filter(is_active=True)
        elif user.role == 'PRINCIPAL':
            school_pks = set(School.objects.filter(principal=user, is_active=True).values_list('pk', flat=True))
            if hasattr(user, 'person') and user.person:
                if user.person.school:
                    school_pks.add(user.person.school.pk)
                prev_pks = user.person.transfer_history.filter(from_school__isnull=False).values_list('from_school', flat=True)
                school_pks.update(prev_pks)
            qs = School.objects.filter(pk__in=school_pks, is_active=True)
        elif hasattr(user, 'person') and user.person:
            school_pks = set()
            if user.person.school:
                school_pks.add(user.person.school.pk)
            prev_pks = user.person.transfer_history.filter(from_school__isnull=False).values_list('from_school', flat=True)
            school_pks.update(prev_pks)
            qs = School.objects.filter(pk__in=school_pks, is_active=True) if school_pks else School.objects.none()
        else:
            return School.objects.none()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(location__icontains=q) |
                Q(region__icontains=q) | Q(division__icontains=q) |
                Q(school_id__icontains=q)
            )
        sort = self.request.GET.get('sort', 'name')
        direction = self.request.GET.get('dir', 'asc')
        sort_map = {'name': 'name', 'type': 'school_type', 'location': 'location', 'status': 'is_active'}
        order_field = sort_map.get(sort, 'name')
        if direction == 'desc':
            order_field = f'-{order_field}'
        return (
            qs.select_related('principal', 'principal__person')
            .annotate(people_count=Count('people', distinct=True))
            .order_by(order_field)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_sort'] = self.request.GET.get('sort', 'name')
        ctx['current_dir'] = self.request.GET.get('dir', 'asc')
        user = self.request.user
        if not (user.is_superuser or user.role == 'ADMIN') and hasattr(user, 'person') and user.person:
            ctx['current_school_id'] = user.person.school.pk if user.person.school else None
            ctx['previous_school_ids'] = set(
                user.person.transfer_history.filter(from_school__isnull=False)
                .values_list('from_school', flat=True)
            )
        return ctx

class SchoolCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = School
    template_name = 'ldp_core/school_form.html'
    form_class = SchoolForm
    success_url = reverse_lazy('ldp_core:school_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .forms import REGION_PROVINCES
        import json
        context['region_provinces'] = json.dumps(REGION_PROVINCES)
        return context

class SchoolUpdateView(LoginRequiredMixin, SchoolEditMixin, UpdateView):
    model = School
    template_name = 'ldp_core/school_form.html'
    form_class = SchoolForm
    success_url = reverse_lazy('ldp_core:school_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .forms import REGION_PROVINCES
        import json
        context['region_provinces'] = json.dumps(REGION_PROVINCES)
        return context

class SchoolDetailView(LoginRequiredMixin, DetailView):
    model = School
    template_name = 'ldp_core/school_detail.html'
    context_object_name = 'school'

class SchoolDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = School
    template_name = 'ldp_core/confirm_delete.html'
    success_url = reverse_lazy('ldp_core:school_list')

class PersonListView(LoginRequiredMixin, ListView):
    model = Person
    template_name = 'ldp_core/person_list.html'
    context_object_name = 'people'
    paginate_by = 50

    def get_queryset(self):
        user = self.request.user
        base_qs = Person.objects.exclude(user__role='ADMIN').exclude(user__is_superuser=True).select_related('user', 'school')
        if user.is_superuser or user.role == 'ADMIN':
            qs = base_qs
        elif hasattr(user, 'person') and user.person.school:
            qs = base_qs.filter(school=user.person.school)
        else:
            return Person.objects.none()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) |
                Q(user__username__icontains=q) | Q(school__name__icontains=q) |
                Q(type__icontains=q)
            )
        school_filter = self.request.GET.get('school', '').strip()
        if school_filter:
            qs = qs.filter(school__pk=school_filter)
        sort = self.request.GET.get('sort', 'name')
        direction = self.request.GET.get('dir', 'asc')
        sort_map = {'name': 'user__last_name', 'type': 'type', 'school': 'school__name'}
        order_field = sort_map.get(sort, 'user__last_name')
        if direction == 'desc':
            order_field = f'-{order_field}'
        return qs.annotate(activity_count=Count('activities', distinct=True)).order_by(order_field)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_sort'] = self.request.GET.get('sort', 'name')
        ctx['current_dir'] = self.request.GET.get('dir', 'asc')
        ctx['school_filter'] = self.request.GET.get('school', '')
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            ctx['school_options'] = list(
                School.objects.filter(is_active=True).order_by('name').values('pk', 'name')
            )
        return ctx
class PersonDetailView(LoginRequiredMixin, DetailView):
    model = Person
    template_name = 'ldp_core/person_detail.html'
    context_object_name = 'person'

    def get_context_data(self, **kwargs):
        from datetime import date
        ctx = super().get_context_data(**kwargs)
        ctx['today'] = date.today()
        return ctx

class PersonCreateView(LoginRequiredMixin, PrincipalOrAdminMixin, CreateView):
    model = Person
    form_class = PersonCreateForm
    template_name = 'ldp_core/person_form.html'
    success_url = reverse_lazy('ldp_core:person_list')

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if (
            user.is_authenticated
            and user.role == 'PRINCIPAL'
            and not user.is_superuser
            and (not hasattr(user, 'person') or user.person.school_id is None)
        ):
            raise PermissionDenied('A school assignment is required to add participants.')
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            return True
        return (
            user.role == 'PRINCIPAL'
            and hasattr(user, 'person')
            and user.person.school_id is not None
        )

    def _get_principal_school(self):
        user = self.request.user
        if user.role == 'PRINCIPAL' and not user.is_superuser and hasattr(user, 'person') and user.person.school:
            return user.person.school
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        school = self._get_principal_school()
        if school:
            kwargs['principal_school'] = school
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        username = self.object.user.username
        messages.success(
            self.request,
            f'Participant created successfully. Their username is {username}. '
            'Share the temporary password securely; they must change it at first login.',
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['principal_school'] = self._get_principal_school()
        return context

class PersonUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Person
    form_class = PersonUpdateForm
    template_name = 'ldp_core/person_edit.html'
    success_url = reverse_lazy('ldp_core:person_list')

    def get_success_url(self):
        return reverse_lazy('ldp_core:person_detail', kwargs={'pk': self.object.pk})

class PersonDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Person
    template_name = 'ldp_core/confirm_delete.html'
    success_url = reverse_lazy('ldp_core:person_list')

    def delete(self, request, *args, **kwargs):
        person = self.get_object()
        user = person.user
        response = super().delete(request, *args, **kwargs)
        if user:
            user.delete()  # Manually clean up User object.
        return response

ACTIVITY_SORT_FIELDS = {
    'name': 'name',
    'date': 'date',
    'school': 'school__name',
    'approval': 'is_approved',
}


def visible_activities_for(user):
    """Return only activities the user is authorized to view."""
    if user.is_superuser or user.role == 'ADMIN':
        return Activity.objects.all()
    if not hasattr(user, 'person'):
        return Activity.objects.none()

    visibility = Q(participants=user.person)
    if user.person.school:
        visibility |= Q(school=user.person.school)
    return Activity.objects.filter(visibility).distinct()


def activity_search_queryset(user, query='', sort='date', direction='desc'):
    queryset = visible_activities_for(user)
    query = query.strip()
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(school__name__icontains=query)
            | Q(description__icontains=query)
        )

    order_field = ACTIVITY_SORT_FIELDS.get(sort, 'date')
    if direction == 'desc':
        order_field = f'-{order_field}'
    return (
        queryset.select_related('school', 'school__principal', 'approved_by')
        .annotate(participant_count=Count('participants', distinct=True))
        .order_by(order_field, 'pk')
    )


def activity_list_context(queryset, query, sort, direction, page_number):
    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(page_number)
    return {
        'activities': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': page_obj.has_other_pages(),
        'today': date.today(),
        'search_query': query,
        'current_sort': sort,
        'current_dir': direction,
    }


class ActivityListView(LoginRequiredMixin, ListView):
    model = Activity
    template_name = 'ldp_core/activity_list.html'
    context_object_name = 'activities'
    paginate_by = 50

    def get_queryset(self):
        sort = self.request.GET.get('sort', 'date')
        direction = self.request.GET.get('dir', 'desc')
        return activity_search_queryset(
            self.request.user,
            self.request.GET.get('q', ''),
            sort,
            direction,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['today'] = date.today()
        ctx['search_query'] = self.request.GET.get('q', '').strip()
        ctx['current_sort'] = self.request.GET.get('sort', 'date')
        ctx['current_dir'] = self.request.GET.get('dir', 'desc')
        return ctx


@login_required
def activity_live_search(request):
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'date')
    direction = request.GET.get('dir', 'desc')
    queryset = activity_search_queryset(request.user, query, sort, direction)
    context = activity_list_context(
        queryset,
        query,
        sort,
        direction,
        request.GET.get('page', 1),
    )

    suggestions = []
    if len(query) >= 2:
        for activity in queryset[:8]:
            suggestions.append({
                'label': activity.name,
                'school': activity.school.name if activity.school else 'Global Event',
                'url': reverse('ldp_core:activity_detail', args=[activity.pk]),
            })

    return JsonResponse({
        'html': render_to_string(
            'ldp_core/partials/activity_results.html',
            context,
            request=request,
        ),
        'suggestions': suggestions,
        'count': context['paginator'].count,
        'query': query,
    })


class ActivityEditMixin(UserPassesTestMixin):
    """Allows admin OR principal of the activity's school."""
    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            return True
        if user.role == 'PRINCIPAL':
            obj = self.get_object() if hasattr(self, 'kwargs') and self.kwargs else None
            if obj is None:
                # For CreateView there's no object yet — allow all principals
                return True
            return obj.school and obj.school.principal == user
        return False


class ActivityCreateView(LoginRequiredMixin, PrincipalOrAdminMixin, CreateView):
    model = Activity
    template_name = 'ldp_core/activity_form.html'
    form_class = ActivityForm
    success_url = reverse_lazy('ldp_core:activity_list')

    def _get_principal_school(self):
        user = self.request.user
        if user.role == 'PRINCIPAL' and not user.is_superuser and hasattr(user, 'person') and user.person.school:
            return user.person.school
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        school = self._get_principal_school()
        if school:
            kwargs['principal_school'] = school
        return kwargs

    def form_valid(self, form):
        activity = form.save(commit=False)
        school = self._get_principal_school()
        if school:
            activity.school = school
            activity.is_approved = True
            activity.approved_by = self.request.user
        activity.save()
        form.save_m2m()  # needed for M2M save after commit=False
        # Set participants from the cleaned form data
        participants = form.cleaned_data.get('participants', [])
        activity.participants.set(participants)
        return HttpResponseRedirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = self._get_principal_school()
        context['is_principal'] = school is not None
        import json
        if not school:
            mapping = {}
            for s in School.objects.all():
                if s.principal_id:
                    mapping[s.id] = s.principal_id
            context['school_principal_mapping'] = json.dumps(mapping)
        return context


class ActivityUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Activity
    template_name = 'ldp_core/activity_form.html'
    form_class = ActivityForm
    success_url = reverse_lazy('ldp_core:activity_list')

    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            return True
        if user.role == 'PRINCIPAL':
            activity = self.get_object()
            return activity.school and activity.school.principal == user
        return False

    def _get_principal_school(self):
        user = self.request.user
        if user.role == 'PRINCIPAL' and not user.is_superuser and hasattr(user, 'person') and user.person.school:
            return user.person.school
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        school = self._get_principal_school()
        if school:
            kwargs['principal_school'] = school
        return kwargs

    def form_valid(self, form):
        activity = form.save(commit=False)
        school = self._get_principal_school()
        if school:
            activity.school = school
            activity.is_approved = True
            activity.approved_by = self.request.user
        activity.save()
        participants = form.cleaned_data.get('participants', [])
        activity.participants.set(participants)
        return HttpResponseRedirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = self._get_principal_school()
        context['is_principal'] = school is not None
        import json
        if not school:
            mapping = {}
            for s in School.objects.all():
                if s.principal_id:
                    mapping[s.id] = s.principal_id
            context['school_principal_mapping'] = json.dumps(mapping)
        return context


class ActivityDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Activity
    template_name = 'ldp_core/confirm_delete.html'
    success_url = reverse_lazy('ldp_core:activity_list')

    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            return True
        if user.role == 'PRINCIPAL':
            activity = self.get_object()
            return activity.school and activity.school.principal == user
        return False


class ActivityDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Activity
    template_name = 'ldp_core/activity_detail.html'
    context_object_name = 'activity'

    def get_context_data(self, **kwargs):
        from datetime import date
        ctx = super().get_context_data(**kwargs)
        ctx['today'] = date.today()
        return ctx

    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.role in ('ADMIN', 'PRINCIPAL'):
            return True
        activity = self.get_object()
        # Allow participants and users in the same school
        if hasattr(user, 'person'):
            if activity.participants.filter(pk=user.person.pk).exists():
                return True
            if activity.school and user.person.school == activity.school:
                return True
        return False

def _profile_field_changes(person):
    field_labels = {
        'first_name': 'First name',
        'last_name': 'Last name',
        'email': 'Email address',
        'contact_number': 'Contact number',
        'address': 'Address',
        'bio': 'Bio',
        'student_id': 'Student / Scholar ID',
        'year_level': 'Year level / Grade',
        'course_program': 'Course / Program',
        'section': 'Section / Batch',
        'scholarship_type': 'Scholarship type / Award',
        'year_started': 'Year started',
        'year_ended': 'Year ended / Graduated',
    }
    user_fields = {'first_name', 'last_name', 'email'}
    changes = person.pending_changes if isinstance(person.pending_changes, dict) else {}
    changed_fields = []
    for field, label in field_labels.items():
        if field not in changes:
            continue
        current = getattr(person.user, field, '') if field in user_fields and person.user else getattr(person, field, '')
        requested = changes.get(field)
        if (current or '') != (requested or ''):
            changed_fields.append({
                'label': label,
                'current': current or '—',
                'requested': requested or '—',
            })
    return changed_fields


@login_required
def change_management(request):
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        messages.error(request, "Access denied.")
        return HttpResponseRedirect(reverse_lazy('ldp_core:dashboard'))
    pending = list(Person.objects.filter(is_pending_approval=True).select_related('user', 'school'))
    for person in pending:
        person.changed_fields = _profile_field_changes(person)
    return render(request, 'ldp_core/change_management.html', {'pending': pending})


@login_required
def approve_profile_update(request, pk):
    person = get_object_or_404(Person, pk=pk)
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        messages.error(request, "You do not have permission to approve profile updates.")
        return HttpResponseRedirect(reverse_lazy('ldp_core:person_list'))
        
    if person.is_pending_approval and isinstance(person.pending_changes, dict):
        changes = person.pending_changes
        if person.user:
            person.user.first_name = changes.get('first_name', person.user.first_name)
            person.user.last_name = changes.get('last_name', person.user.last_name)
            if changes.get('email'):
                person.user.email = changes.get('email')
            person.user.save()

        person.contact_number = changes.get('contact_number', person.contact_number)
        person.address = changes.get('address', person.address)
        person.bio = changes.get('bio', person.bio)
        person.student_id = changes.get('student_id', person.student_id)
        person.year_level = changes.get('year_level', person.year_level)
        person.course_program = changes.get('course_program', person.course_program)
        person.section = changes.get('section', person.section)
        person.scholarship_type = changes.get('scholarship_type', person.scholarship_type)
        person.year_started = changes.get('year_started', person.year_started)
        person.year_ended = changes.get('year_ended', person.year_ended)
        
        person.pending_changes = None
        person.is_pending_approval = False
        person.save()
        messages.success(request, f"Profile updates for {person.user.get_full_name() if person.user else ''} approved.")
    else:
        messages.info(request, "No pending profile updates found.")
        
    return HttpResponseRedirect(reverse_lazy('ldp_core:change_management'))


@login_required
def reject_profile_update(request, pk):
    person = get_object_or_404(Person, pk=pk)
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        messages.error(request, "Access denied.")
        return HttpResponseRedirect(reverse_lazy('ldp_core:person_list'))
    
    person.pending_changes = None
    person.is_pending_approval = False
    person.save()
    messages.warning(request, f"Profile changes for {person.user.get_full_name() if person.user else ''} rejected and discarded.")
    return HttpResponseRedirect(reverse_lazy('ldp_core:change_management'))


@login_required
def toggle_activity_approval(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    # Check if user is either Admin OR the principal of the school
    is_admin = request.user.is_superuser or request.user.role == 'ADMIN'
    is_principal_of_school = request.user.role == 'PRINCIPAL' and activity.school and activity.school.principal == request.user

    if is_admin or is_principal_of_school:
        activity.is_approved = not activity.is_approved
        
        # If toggling ON, ensure approved_by is set to the person who clicked it
        if activity.is_approved:
            activity.approved_by = request.user
        
        activity.save()
        messages.success(request, f"Activity '{activity.name}' approval status changed.")
    else:
        messages.error(request, "You do not have permission to approve this activity.")
    
    return HttpResponseRedirect(reverse_lazy('ldp_core:activity_list'))


MIGRATION_DEFAULT_MAPPING = {
    'schools': {'school_name': 'name', 'schoolName': 'name', 'emis_no': 'school_id', 'school_code': 'school_id', 'type': 'school_type', 'municipality': 'location', 'city': 'location', 'contact_email': 'email', 'contact_number': 'phone', 'telephone': 'phone', 'active': 'is_active'},
    'users': {'user_name': 'username', 'login': 'username', 'given_name': 'first_name', 'surname': 'last_name', 'mail': 'email', 'user_type': 'role', 'account_type': 'role', 'active': 'is_active'},
    'people': {'person_type': 'type', 'learner_type': 'type', 'school': 'school_name', 'schoolName': 'school_name', 'school_code': 'school_id', 'user': 'username', 'user_name': 'username', 'student_no': 'student_id', 'lrn': 'student_id', 'grade_level': 'year_level', 'program': 'course_program', 'batch': 'section'},
    'activities': {'title': 'name', 'activity_name': 'name', 'activity_date': 'date', 'notes': 'description', 'school': 'school_name', 'schoolName': 'school_name', 'school_code': 'school_id', 'approved': 'is_approved'},
    'awards': {'title': 'award_title', 'name': 'award_title', 'level': 'award_level', 'year': 'year_awarded', 'body': 'awarding_body', 'organization': 'awarding_body', 'notes': 'description', 'recipient': 'recipient_name', 'awardee': 'recipient_name', 'recipient_user': 'recipient_username', 'school': 'school_name', 'schoolName': 'school_name', 'school_code': 'school_id'},
}


def _migration_entity(model_name, fallback=''):
    label = f'{model_name or fallback}'.lower()
    if 'leadershipaward' in label or 'award' in label:
        return 'awards'
    if 'activity' in label:
        return 'activities'
    if 'person' in label or 'profile' in label or 'student' in label or 'scholar' in label:
        return 'people'
    if 'user' in label or 'auth.' in label:
        return 'users'
    if 'school' in label:
        return 'schools'
    return ''


def _migration_rows(payload):
    rows = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            entity = _migration_entity('', key)
            if entity and isinstance(value, list):
                rows.extend({'entity': entity, 'legacy_pk': item.get('id') or item.get('pk'), 'fields': item} for item in value if isinstance(item, dict))
        return rows
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            if 'model' in item and 'fields' in item:
                rows.append({'entity': _migration_entity(item.get('model')), 'legacy_pk': item.get('pk'), 'fields': item.get('fields') if isinstance(item.get('fields'), dict) else {}})
            else:
                rows.append({'entity': _migration_entity(item.get('model') or item.get('entity') or item.get('type')), 'legacy_pk': item.get('id') or item.get('pk'), 'fields': item})
    return rows


def _mapped_fields(entity, fields, custom_mapping):
    mapping = {**MIGRATION_DEFAULT_MAPPING.get(entity, {}), **custom_mapping.get(entity, {})}
    return {mapping.get(key, key): value for key, value in fields.items()}


def _bool_value(value, default=False):
    if value in (True, False):
        return value
    if value is None or value == '':
        return default
    return str(value).strip().lower() in {'1', 'true', 'yes', 'y', 'active', 'enabled'}


def _role_value(value):
    User = get_user_model()
    role = str(value or User.Role.VIEWER).upper()
    return role if role in dict(User.Role.choices) else User.Role.VIEWER


def _resolve_school(row):
    school_id = row.get('school_id') or row.get('school_code')
    if school_id:
        school = School.objects.filter(Q(school_id=school_id) | Q(pk=school_id)).first()
        if school:
            return school
    school_name = row.get('school_name') or row.get('school')
    if school_name:
        return School.objects.filter(name__iexact=str(school_name).strip()).first()
    return None


def _preview_action(model, lookup, conflict_strategy):
    exists = model.objects.filter(**lookup).exists()
    if exists and conflict_strategy == 'create_only':
        return 'skipped'
    if not exists and conflict_strategy == 'update_only':
        return 'skipped'
    return 'updated' if exists else 'created'


def _bump_migration(report, entity, action, sample=None):
    if action in {'created', 'updated'}:
        report[action] += 1
        report['entities'][entity][action] += 1
    else:
        report['skipped'] += 1
        report['entities'][entity]['skipped'] += 1
    if sample and len(report['entities'][entity]['samples']) < 3:
        report['entities'][entity]['samples'].append(sample)


def _apply_or_preview_legacy_migration(payload, selected_entities, custom_mapping, conflict_strategy, preview=True):
    User = get_user_model()
    report = {
        'preview': preview,
        'strategy': conflict_strategy,
        'source_rows': 0,
        'compatible_rows': 0,
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'entities': {entity: {'created': 0, 'updated': 0, 'skipped': 0, 'samples': []} for entity in selected_entities},
    }
    rows_by_entity = {entity: [] for entity in selected_entities}
    for row in _migration_rows(payload):
        report['source_rows'] += 1
        entity = row.get('entity')
        if entity in rows_by_entity:
            mapped = _mapped_fields(entity, row.get('fields', {}), custom_mapping)
            mapped['legacy_pk'] = row.get('legacy_pk')
            rows_by_entity[entity].append(mapped)
            report['compatible_rows'] += 1

    from django.db import transaction
    with transaction.atomic():
        for row in rows_by_entity.get('schools', []):
            name = str(row.get('name') or '').strip()
            if not name:
                _bump_migration(report, 'schools', 'skipped', {'reason': 'Missing school name'})
                continue
            lookup = {'school_id': row.get('school_id')} if row.get('school_id') else {'name': name}
            action = _preview_action(School, lookup, conflict_strategy)
            if action == 'skipped':
                _bump_migration(report, 'schools', action, {'name': name, 'match': lookup})
                continue
            defaults = {'name': name, 'school_type': row.get('school_type', ''), 'category': row.get('category', ''), 'address': row.get('address', ''), 'location': row.get('location', 'Philippines') or 'Philippines', 'district': row.get('district', ''), 'division': row.get('division', ''), 'province': row.get('province', ''), 'region': row.get('region', ''), 'email': row.get('email', ''), 'phone': row.get('phone', ''), 'website': row.get('website', ''), 'is_active': _bool_value(row.get('is_active'), True)}
            if not preview:
                School.objects.update_or_create(defaults=defaults, **lookup)
            _bump_migration(report, 'schools', action, {'name': name, 'match': lookup})

        for row in rows_by_entity.get('users', []):
            username = str(row.get('username') or row.get('email') or '').strip()
            if not username:
                _bump_migration(report, 'users', 'skipped', {'reason': 'Missing username'})
                continue
            action = _preview_action(User, {'username': username}, conflict_strategy)
            if action == 'skipped':
                _bump_migration(report, 'users', action, {'username': username})
                continue
            defaults = {'first_name': row.get('first_name', ''), 'last_name': row.get('last_name', ''), 'email': row.get('email', ''), 'role': _role_value(row.get('role')), 'is_active': _bool_value(row.get('is_active'), True)}
            if not preview:
                user, created = User.objects.get_or_create(username=username, defaults=defaults)
                if not created:
                    for key, value in defaults.items():
                        setattr(user, key, value)
                if created:
                    user.set_unusable_password()
                user.save()
            _bump_migration(report, 'users', action, {'username': username, 'role': defaults['role']})

        for row in rows_by_entity.get('people', []):
            username = str(row.get('username') or '').strip()
            user = User.objects.filter(username=username).first() if username else None
            if not user and row.get('email'):
                user = User.objects.filter(email=row.get('email')).first()
            if not user:
                _bump_migration(report, 'people', 'skipped', {'reason': 'No matching user'})
                continue
            action = _preview_action(Person, {'user': user}, conflict_strategy)
            if action == 'skipped':
                _bump_migration(report, 'people', action, {'username': user.username})
                continue
            school = _resolve_school(row)
            defaults = {'type': row.get('type') or Person.Type.STUDENT, 'school': school, 'contact_number': row.get('contact_number', ''), 'address': row.get('address', ''), 'bio': row.get('bio', ''), 'student_id': row.get('student_id', ''), 'year_level': row.get('year_level', ''), 'course_program': row.get('course_program', ''), 'section': row.get('section', ''), 'scholarship_type': row.get('scholarship_type', ''), 'year_started': row.get('year_started', ''), 'year_ended': row.get('year_ended', '')}
            if not preview:
                Person.objects.update_or_create(user=user, defaults=defaults)
            _bump_migration(report, 'people', action, {'username': user.username, 'school': school.name if school else ''})

        for row in rows_by_entity.get('activities', []):
            name = str(row.get('name') or '').strip()
            date = row.get('date')
            if not name or not date:
                _bump_migration(report, 'activities', 'skipped', {'reason': 'Missing name/date'})
                continue
            action = _preview_action(Activity, {'name': name, 'date': date}, conflict_strategy)
            if action == 'skipped':
                _bump_migration(report, 'activities', action, {'name': name})
                continue
            defaults = {'description': row.get('description', ''), 'school': _resolve_school(row), 'is_approved': _bool_value(row.get('is_approved'), False)}
            if not preview:
                Activity.objects.update_or_create(name=name, date=date, defaults=defaults)
            _bump_migration(report, 'activities', action, {'name': name, 'date': date})

        for row in rows_by_entity.get('awards', []):
            title = str(row.get('award_title') or '').strip()
            year = str(row.get('year_awarded') or '').strip()
            recipient = Person.objects.filter(user__username=row.get('recipient_username')).first() if row.get('recipient_username') else None
            if not recipient and row.get('recipient_id'):
                recipient = Person.objects.filter(pk=row.get('recipient_id')).first()
            if not recipient or not title or not year:
                _bump_migration(report, 'awards', 'skipped', {'title': title, 'reason': 'Missing recipient/title/year'})
                continue
            action = _preview_action(LeadershipAward, {'recipient': recipient, 'award_title': title, 'year_awarded': year}, conflict_strategy)
            if action == 'skipped':
                _bump_migration(report, 'awards', action, {'title': title})
                continue
            defaults = {'award_level': row.get('award_level') or LeadershipAward.AwardLevel.SCHOOL, 'awarding_body': row.get('awarding_body', ''), 'description': row.get('description', ''), 'school': _resolve_school(row) or recipient.school}
            if not preview:
                LeadershipAward.objects.update_or_create(recipient=recipient, award_title=title, year_awarded=year, defaults=defaults)
            _bump_migration(report, 'awards', action, {'title': title, 'recipient': str(recipient)})

        if preview:
            transaction.set_rollback(True)
    return report


@admin_required
def legacy_migration(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not operation_enabled('import'):
        messages.error(request, 'Data imports are disabled in System Settings.')
        return redirect('ldp_core:bulk_import_dashboard')
    form = LegacyMigrationForm(request.POST, request.FILES)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect('ldp_core:bulk_import_dashboard')
    payload = form.payload
    selected_entities = form.cleaned_data['entities']
    disabled_entities = [
        entity for entity in selected_entities
        if not operation_enabled('import', entity)
    ]
    if disabled_entities:
        messages.error(
            request,
            f"Enable these modules in System Settings before migration: {', '.join(disabled_entities)}.",
        )
        return redirect('ldp_core:bulk_import_dashboard')
    conflict_strategy = form.cleaned_data['conflict_strategy']
    custom_mapping = form.cleaned_data['field_mapping']
    preview = form.cleaned_data['migration_mode'] == 'preview'
    try:
        report = _apply_or_preview_legacy_migration(payload, selected_entities, custom_mapping, conflict_strategy, preview=preview)
    except Exception:
        messages.error(request, 'Migration could not be completed. No partial changes were saved.')
        return redirect('ldp_core:bulk_import_dashboard')
    request.session['migration_report'] = report
    request.session.modified = True
    if preview:
        messages.info(request, f"Migration preview complete: {report['compatible_rows']} compatible row(s), {report['created']} create candidate(s), {report['updated']} update candidate(s), {report['skipped']} skipped.")
    else:
        messages.success(request, f"Migration applied: {report['created']} created, {report['updated']} updated, {report['skipped']} skipped.")
    return redirect('ldp_core:bulk_import_dashboard')


@admin_required
def settings_page(request):
    configuration = get_system_settings()
    if request.method == 'POST':
        form = SystemSettingsForm(request.POST, instance=configuration)
        if form.is_valid():
            configuration = form.save(commit=False)
            configuration.updated_by = request.user
            configuration.save()
            messages.success(request, 'System settings updated for all administrators.')
            return redirect('ldp_core:settings')
    else:
        form = SystemSettingsForm(instance=configuration)

    context = {
        'form': form,
        'configuration': configuration,
        'school_count': School.objects.count(),
        'user_count': get_user_model().objects.count(),
        'activity_count': Activity.objects.count(),
        'award_count': LeadershipAward.objects.count(),
    }
    return render(request, 'ldp_core/settings.html', context)


@admin_required
def export_data(request, data_type):
    data_type = data_type.lower()
    if not operation_enabled('export', data_type):
        messages.error(request, f'{data_type.title()} export is disabled in System Settings.')
        return redirect('ldp_core:bulk_import_dashboard')
    if data_type == 'schools':
        rows = list(School.objects.values('name', 'school_id', 'school_type', 'category', 'address', 'location', 'district', 'division', 'province', 'region', 'email', 'phone', 'website', 'founded_year', 'is_active'))
    elif data_type == 'users':
        User = get_user_model()
        rows = list(User.objects.values('username', 'first_name', 'last_name', 'email', 'role', 'is_active'))
    elif data_type == 'activities':
        rows = list(Activity.objects.values('name', 'date', 'description', 'school__school_id', 'is_approved', 'approved_by__username'))
    elif data_type == 'awards':
        rows = list(
            LeadershipAward.objects.values(
                'recipient__user__username',
                'award_title',
                'award_level',
                'year_awarded',
                'awarding_body',
                'description',
                'school__school_id',
            )
        )
    else:
        messages.error(request, 'Unsupported export type.')
        return redirect('ldp_core:bulk_import_dashboard')

    payload = {'schema': 'ldp-data-interchange', 'version': 1, 'entity': data_type, 'records': rows}
    response = HttpResponse(content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="ldp-{data_type}-v1.json"'
    response.write(json.dumps(payload, default=str, indent=2))
    return response


@admin_required
def import_data(request, data_type):
    messages.info(
        request,
        'Direct JSON imports were retired. Use the validated Excel workflow or Advanced legacy migration.',
    )
    return redirect('ldp_core:bulk_import_dashboard')


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Person
    form_class = UserProfileUpdateForm
    template_name = 'ldp_core/profile_form.html'
    success_url = reverse_lazy('ldp_core:dashboard')

    def get_object(self, queryset=None):
        person, created = Person.objects.get_or_create(user=self.request.user)
        return person

    def form_valid(self, form):
        messages.success(self.request, "Your profile has been updated successfully!")
        return super().form_valid(form)


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'registration/change_password.html'
    success_url = reverse_lazy('ldp_core:dashboard')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save()
        return response


# ─── Leadership Awards ───────────────────────────────────────────────────────

class AwardListView(LoginRequiredMixin, ListView):
    model = LeadershipAward
    template_name = 'ldp_core/award_list.html'
    context_object_name = 'awards'
    paginate_by = 50

    def get_queryset(self):
        user = self.request.user
        qs = LeadershipAward.objects.select_related('recipient__user', 'school')
        if not (user.is_superuser or getattr(user, 'role', None) == 'ADMIN'):
            school = user.person.school if hasattr(user, 'person') else None
            qs = qs.filter(school=school) if school else LeadershipAward.objects.none()
        search = self.request.GET.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(award_title__icontains=search) |
                Q(recipient__user__first_name__icontains=search) |
                Q(recipient__user__last_name__icontains=search) |
                Q(year_awarded__icontains=search) |
                Q(awarding_body__icontains=search) |
                Q(school__name__icontains=search)
            )
        sort = self.request.GET.get('sort', 'year')
        direction = self.request.GET.get('dir', 'desc')
        sort_map = {
            'year': 'year_awarded', 'title': 'award_title',
            'level': 'award_level', 'recipient': 'recipient__user__last_name',
            'school': 'school__name',
        }
        order_field = sort_map.get(sort, 'year_awarded')
        if direction == 'desc':
            order_field = f'-{order_field}'
        return qs.order_by(order_field)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['can_manage'] = user.is_superuser or getattr(user, 'role', None) in ('ADMIN', 'PRINCIPAL')
        ctx['principal_school'] = None
        if getattr(user, 'role', None) == 'PRINCIPAL':
            try:
                ctx['principal_school'] = user.person.school
            except Exception:
                pass
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_sort'] = self.request.GET.get('sort', 'year')
        ctx['current_dir'] = self.request.GET.get('dir', 'desc')
        return ctx


class AwardCreateView(LoginRequiredMixin, PrincipalOrAdminMixin, CreateView):
    model = LeadershipAward
    form_class = LeadershipAwardForm
    template_name = 'ldp_core/award_form.html'
    success_url = reverse_lazy('ldp_core:award_list')

    def _get_principal_school(self):
        user = self.request.user
        if not user.is_superuser and getattr(user, 'role', None) == 'PRINCIPAL':
            try:
                return user.person.school
            except Exception:
                pass
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['principal_school'] = self._get_principal_school()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['principal_school'] = self._get_principal_school()
        return ctx

    def form_valid(self, form):
        ps = self._get_principal_school()
        if ps and not form.instance.school_id:
            form.instance.school = ps
        messages.success(self.request, 'Leadership Award recorded successfully.')
        return super().form_valid(form)


class AwardUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = LeadershipAward
    form_class = LeadershipAwardForm
    template_name = 'ldp_core/award_form.html'
    success_url = reverse_lazy('ldp_core:award_list')

    def test_func(self):
        user = self.request.user
        if user.is_superuser or getattr(user, 'role', None) == 'ADMIN':
            return True
        if getattr(user, 'role', None) == 'PRINCIPAL':
            try:
                return self.get_object().school == user.person.school
            except Exception:
                pass
        return False

    def _get_principal_school(self):
        user = self.request.user
        if not user.is_superuser and getattr(user, 'role', None) == 'PRINCIPAL':
            try:
                return user.person.school
            except Exception:
                pass
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['principal_school'] = self._get_principal_school()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['principal_school'] = self._get_principal_school()
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Award updated successfully.')
        return super().form_valid(form)


class AwardDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = LeadershipAward
    template_name = 'ldp_core/award_confirm_delete.html'
    success_url = reverse_lazy('ldp_core:award_list')

    def test_func(self):
        user = self.request.user
        if user.is_superuser or getattr(user, 'role', None) == 'ADMIN':
            return True
        if getattr(user, 'role', None) == 'PRINCIPAL':
            try:
                return self.get_object().school == user.person.school
            except Exception:
                pass
        return False


# ── Principal Assignment History CRUD ────────────────────────────────────────

class AssignmentHistoryMixin(UserPassesTestMixin):
    """Allows admin/superuser OR the current principal of the school."""
    def _get_school(self):
        school_pk = self.kwargs.get('school_pk')
        return get_object_or_404(School, pk=school_pk)

    def test_func(self):
        user = self.request.user
        if user.is_superuser or getattr(user, 'role', None) == 'ADMIN':
            return True
        if getattr(user, 'role', None) == 'PRINCIPAL':
            school = self._get_school()
            return school.principal == user
        return False


class AssignmentHistoryAddView(LoginRequiredMixin, AssignmentHistoryMixin, CreateView):
    model = SchoolPrincipalHistory
    form_class = SchoolPrincipalHistoryForm
    template_name = 'ldp_core/assignment_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self._get_school()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['school'] = self._get_school()
        ctx['is_add'] = True
        return ctx

    def form_valid(self, form):
        school = self._get_school()
        entry = form.save(commit=False)
        entry.school = school
        # Auto-fill principal_name from selected principal user if not provided
        if entry.principal and not entry.principal_name:
            entry.principal_name = entry.principal.get_full_name() or entry.principal.username
        entry.save()
        messages.success(self.request, 'Assignment entry added successfully.')
        return redirect('ldp_core:school_detail', pk=school.pk)


class AssignmentHistoryEditView(LoginRequiredMixin, AssignmentHistoryMixin, UpdateView):
    model = SchoolPrincipalHistory
    form_class = SchoolPrincipalHistoryForm
    template_name = 'ldp_core/assignment_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self._get_school()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['school'] = self._get_school()
        ctx['is_add'] = False
        return ctx

    def form_valid(self, form):
        school = self._get_school()
        entry = form.save(commit=False)
        # Sync principal_name if principal changed
        if entry.principal and not entry.principal_name:
            entry.principal_name = entry.principal.get_full_name() or entry.principal.username
        entry.save()
        messages.success(self.request, 'Assignment entry updated.')
        return redirect('ldp_core:school_detail', pk=school.pk)


class AssignmentHistoryDeleteView(LoginRequiredMixin, AssignmentHistoryMixin, DeleteView):
    model = SchoolPrincipalHistory
    template_name = 'ldp_core/assignment_confirm_delete.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['school'] = self._get_school()
        return ctx

    def get_success_url(self):
        return reverse_lazy('ldp_core:school_detail', kwargs={'pk': self.kwargs['school_pk']})


# ── Person Transfer CRUD ──────────────────────────────────────────────────────

class TransferMixin(UserPassesTestMixin):
    """Admin/superuser, or a Principal managing the person's current school."""
    def _get_transfer_person(self):
        person_pk = self.kwargs.get('person_pk')
        if person_pk:
            return get_object_or_404(Person, pk=person_pk)
        # For edit/delete, get person from the transfer record
        obj = self.get_object()
        return obj.person

    def test_func(self):
        user = self.request.user
        if user.is_superuser or getattr(user, 'role', None) == 'ADMIN':
            return True
        if getattr(user, 'role', None) == 'PRINCIPAL':
            try:
                person = self._get_transfer_person()
            except Exception:
                return False
            # Principals cannot transfer admins or superusers
            if person.user and (person.user.is_superuser or getattr(person.user, 'role', None) == 'ADMIN'):
                return False
            # Principal must manage the person's current school
            if person.school and person.school.principal == user:
                return True
        return False


class PersonTransferView(LoginRequiredMixin, TransferMixin, CreateView):
    """Record a new school transfer for a person."""
    model = PersonTransferHistory
    form_class = PersonTransferForm
    template_name = 'ldp_core/transfer_form.html'

    def _get_person(self):
        return get_object_or_404(Person, pk=self.kwargs['person_pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['person'] = self._get_person()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['person'] = self._get_person()
        return ctx

    def form_valid(self, form):
        person = self._get_person()
        entry = form.save(commit=False)
        entry.person = person
        entry.from_school = person.school
        entry.processed_by = self.request.user
        entry.save()
        # Actually move the person to the new school
        person.school = entry.to_school
        person.save()
        messages.success(
            self.request,
            f'{person} has been transferred to {entry.to_school}.'
        )
        return redirect('ldp_core:person_detail', pk=person.pk)


class TransferEditView(LoginRequiredMixin, TransferMixin, UpdateView):
    """Edit an existing transfer record (admin-only)."""
    model = PersonTransferHistory
    form_class = PersonTransferForm
    template_name = 'ldp_core/transfer_form.html'

    def _get_person(self):
        return get_object_or_404(Person, pk=self.kwargs['person_pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['person'] = None  # no exclusion needed when editing
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['person'] = self._get_person()
        ctx['is_edit'] = True
        return ctx

    def form_valid(self, form):
        person = self._get_person()
        form.save()
        messages.success(self.request, 'Transfer record updated.')
        return redirect('ldp_core:person_detail', pk=person.pk)


class TransferDeleteView(LoginRequiredMixin, TransferMixin, DeleteView):
    """Delete a transfer record (admin-only)."""
    model = PersonTransferHistory
    template_name = 'ldp_core/transfer_confirm_delete.html'

    def _get_person(self):
        return get_object_or_404(Person, pk=self.kwargs['person_pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['person'] = self._get_person()
        return ctx

    def get_success_url(self):
        return reverse_lazy('ldp_core:person_detail', kwargs={'pk': self.kwargs['person_pk']})


# ─── Professional Jobs ────────────────────────────────────────────────────────

class JobAccessMixin(UserPassesTestMixin):
    """Allows admin/superuser OR the professional person themselves."""
    def _get_person(self):
        return get_object_or_404(Person, pk=self.kwargs['person_pk'])

    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            return True
        person = self._get_person()
        return hasattr(user, 'person') and user.person == person


class JobAddView(LoginRequiredMixin, JobAccessMixin, CreateView):
    model = ProfessionalJob
    form_class = ProfessionalJobForm
    template_name = 'ldp_core/job_form.html'

    def form_valid(self, form):
        job = form.save(commit=False)
        job.person = self._get_person()
        if job.is_current:
            job.end_date = None
        job.save()
        messages.success(self.request, "Job record added successfully.")
        return redirect('ldp_core:person_detail', pk=job.person.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['person'] = self._get_person()
        ctx['is_edit'] = False
        return ctx


class JobEditView(LoginRequiredMixin, JobAccessMixin, UpdateView):
    model = ProfessionalJob
    form_class = ProfessionalJobForm
    template_name = 'ldp_core/job_form.html'

    def get_object(self, queryset=None):
        return get_object_or_404(ProfessionalJob, pk=self.kwargs['pk'],
                                 person__pk=self.kwargs['person_pk'])

    def form_valid(self, form):
        job = form.save(commit=False)
        if job.is_current:
            job.end_date = None
        job.save()
        messages.success(self.request, "Job record updated.")
        return redirect('ldp_core:person_detail', pk=self.kwargs['person_pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['person'] = self._get_person()
        ctx['is_edit'] = True
        return ctx


class JobDeleteView(LoginRequiredMixin, JobAccessMixin, DeleteView):
    model = ProfessionalJob
    template_name = 'ldp_core/job_confirm_delete.html'

    def get_object(self, queryset=None):
        return get_object_or_404(ProfessionalJob, pk=self.kwargs['pk'],
                                 person__pk=self.kwargs['person_pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['person'] = self._get_person()
        return ctx

    def get_success_url(self):
        return reverse_lazy('ldp_core:person_detail', kwargs={'pk': self.kwargs['person_pk']})
