from django.urls import path
from . import views

urlpatterns = [
    path('benchmark/', views.benchmark, name='benchmark'),
    path('health/', views.health_check, name='health-check'),
]
