from django.urls import path
from . import views

app_name = 'ldp_core'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('schools/', views.SchoolListView.as_view(), name='school_list'),
    path('schools/create/', views.SchoolCreateView.as_view(), name='school_create'),
    path('schools/<int:pk>/', views.SchoolDetailView.as_view(), name='school_detail'),
    path('schools/<int:pk>/edit/', views.SchoolUpdateView.as_view(), name='school_update'),
    path('schools/<int:pk>/delete/', views.SchoolDeleteView.as_view(), name='school_delete'),
    path('people/', views.PersonListView.as_view(), name='person_list'),
    path('people/<int:pk>/', views.PersonDetailView.as_view(), name='person_detail'),
    path('people/create/', views.PersonCreateView.as_view(), name='person_create'),
    path('people/<int:pk>/edit/', views.PersonUpdateView.as_view(), name='person_update'),
    path('people/<int:pk>/delete/', views.PersonDeleteView.as_view(), name='person_delete'),
    path('change-management/', views.change_management, name='change_management'),
    path('change-management/<int:pk>/approve/', views.approve_profile_update, name='approve_profile'),
    path('change-management/<int:pk>/reject/', views.reject_profile_update, name='reject_profile'),
    path('activities/', views.ActivityListView.as_view(), name='activity_list'),
    path('activities/create/', views.ActivityCreateView.as_view(), name='activity_create'),
    path('activities/<int:pk>/', views.ActivityDetailView.as_view(), name='activity_detail'),
    path('activities/<int:pk>/edit/', views.ActivityUpdateView.as_view(), name='activity_update'),
    path('activities/<int:pk>/delete/', views.ActivityDeleteView.as_view(), name='activity_delete'),
    path('activities/<int:pk>/approve/', views.toggle_activity_approval, name='activity_approve'),
    path('change-password/', views.CustomPasswordChangeView.as_view(), name='change_password'),
    path('profile/', views.ProfileUpdateView.as_view(), name='profile'),
    path('awards/', views.AwardListView.as_view(), name='award_list'),
    path('awards/create/', views.AwardCreateView.as_view(), name='award_create'),
    path('awards/<int:pk>/edit/', views.AwardUpdateView.as_view(), name='award_update'),
    path('awards/<int:pk>/delete/', views.AwardDeleteView.as_view(), name='award_delete'),
]