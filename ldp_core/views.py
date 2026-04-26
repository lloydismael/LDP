from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from .models import School, Person, Activity, LeadershipAward
from .forms import PersonCreateForm, PersonUpdateForm, ActivityForm, SchoolForm, UserProfileUpdateForm, LeadershipAwardForm
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.db.models import Q

@login_required
def dashboard(request):
    import json
    from datetime import date as _date
    user = request.user
    if user.is_superuser or user.role == 'ADMIN':
        schools_count = School.objects.filter(is_active=True).count()
        people_count = Person.objects.count()
        activities_count = Activity.objects.count()
        cal_qs = Activity.objects.values('pk', 'name', 'date')
    elif hasattr(user, 'person') and user.person and user.person.school:
        schools_count = 1
        people_count = Person.objects.filter(school=user.person.school).count()
        activities_count = Activity.objects.filter(school=user.person.school).count()
        cal_qs = Activity.objects.filter(school=user.person.school).values('pk', 'name', 'date')
    else:
        schools_count = 0
        people_count = 0
        activities_count = 0
        cal_qs = Activity.objects.values('pk', 'name', 'date')

    cal_acts = [{'pk': a['pk'], 'name': a['name'], 'date': a['date'].isoformat()} for a in cal_qs]

    context = {
        'schools_count': schools_count,
        'people_count': people_count,
        'activities_count': activities_count,
        'pending_changes_count': Person.objects.filter(is_pending_approval=True).count() if (user.is_superuser or user.role == 'ADMIN') else 0,
        'cal_activities': json.dumps(cal_acts),
        'today': _date.today().isoformat(),
    }
    return render(request, 'ldp_core/dashboard.html', context)


class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == 'ADMIN'


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
    paginate_by = 100

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            qs = School.objects.filter(is_active=True)
        elif user.role == 'PRINCIPAL':
            qs = School.objects.filter(principal=user, is_active=True)
        elif hasattr(user, 'person') and user.person.school:
            qs = School.objects.filter(pk=user.person.school.pk, is_active=True)
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
        return qs.order_by(order_field)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_sort'] = self.request.GET.get('sort', 'name')
        ctx['current_dir'] = self.request.GET.get('dir', 'asc')
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
    paginate_by = 100

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
        sort = self.request.GET.get('sort', 'name')
        direction = self.request.GET.get('dir', 'asc')
        sort_map = {'name': 'user__last_name', 'type': 'type', 'school': 'school__name'}
        order_field = sort_map.get(sort, 'user__last_name')
        if direction == 'desc':
            order_field = f'-{order_field}'
        return qs.order_by(order_field)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_sort'] = self.request.GET.get('sort', 'name')
        ctx['current_dir'] = self.request.GET.get('dir', 'asc')
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

class ActivityListView(LoginRequiredMixin, ListView):
    model = Activity
    template_name = 'ldp_core/activity_list.html'
    context_object_name = 'activities'
    paginate_by = 100

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            qs = Activity.objects.all()
        else:
            q_filter = Q()
            if hasattr(user, 'person'):
                if user.person.school:
                    q_filter |= Q(school=user.person.school)
                q_filter |= Q(participants=user.person)
            if q_filter:
                qs = Activity.objects.filter(q_filter).distinct()
            else:
                return Activity.objects.none()
        search = self.request.GET.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(school__name__icontains=search) |
                Q(description__icontains=search)
            )
        sort = self.request.GET.get('sort', 'date')
        direction = self.request.GET.get('dir', 'desc')
        sort_map = {'name': 'name', 'date': 'date', 'school': 'school__name', 'approval': 'is_approved'}
        order_field = sort_map.get(sort, 'date')
        if direction == 'desc':
            order_field = f'-{order_field}'
        return qs.order_by(order_field)

    def get_context_data(self, **kwargs):
        from datetime import date
        ctx = super().get_context_data(**kwargs)
        ctx['today'] = date.today()
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_sort'] = self.request.GET.get('sort', 'date')
        ctx['current_dir'] = self.request.GET.get('dir', 'desc')
        return ctx


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

@login_required
def change_management(request):
    if not (request.user.is_superuser or request.user.role == 'ADMIN'):
        messages.error(request, "Access denied.")
        return HttpResponseRedirect(reverse_lazy('ldp_core:dashboard'))
    pending = Person.objects.filter(is_pending_approval=True).select_related('user', 'school')
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
    paginate_by = 100

    def get_queryset(self):
        user = self.request.user
        qs = LeadershipAward.objects.select_related('recipient__user', 'school')
        if not (user.is_superuser or getattr(user, 'role', None) == 'ADMIN'):
            try:
                school = user.person.school
                if school:
                    qs = qs.filter(school=school)
            except Exception:
                pass
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
