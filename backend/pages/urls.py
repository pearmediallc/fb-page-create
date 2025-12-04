from django.urls import path
from . import views

urlpatterns = [
    # Tasks
    path('tasks/', views.tasks_list, name='tasks-list'),
    path('tasks/<str:task_id>/', views.task_detail, name='task-detail'),
    path('tasks/<str:task_id>/start/', views.task_start, name='task-start'),
    path('tasks/<str:task_id>/cancel/', views.task_cancel, name='task-cancel'),

    # Pages
    path('pages/', views.pages_list, name='pages-list'),
    path('pages/<str:page_id>/invite/', views.invite_person, name='invite-person'),
    path('pages/<str:page_id>/invites/', views.page_invites, name='page-invites'),

    # Invites
    path('invites/', views.invites_list, name='invites-list'),
    path('invites/<str:invite_id>/accept/', views.accept_invite, name='accept-invite'),
    path('invites/<str:invite_id>/decline/', views.decline_invite, name='decline-invite'),

    # Profiles
    path('profiles/', views.profiles_list, name='profiles-list'),

    # Reports
    path('tasks/efficiency_report/', views.efficiency_report, name='efficiency-report'),

    # Automation
    path('automation/benchmark/', views.benchmark, name='benchmark'),
    path('automation/health/', views.health_check, name='health-check'),
    path('automation/test-invite/', views.test_invite_access, name='test-invite'),
]
