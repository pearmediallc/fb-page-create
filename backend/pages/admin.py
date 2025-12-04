from django.contrib import admin
from .models import PageGenerationTask, GeneratedPage, PerformanceMetric


@admin.register(PageGenerationTask)
class PageGenerationTaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'base_name', 'count', 'status', 'created_at', 'total_time_seconds']
    list_filter = ['status', 'created_at']
    search_fields = ['base_name']
    readonly_fields = ['id', 'created_at', 'started_at', 'completed_at']


@admin.register(GeneratedPage)
class GeneratedPageAdmin(admin.ModelAdmin):
    list_display = ['name', 'task', 'status', 'sequence_number', 'duration_seconds']
    list_filter = ['status', 'task']
    search_fields = ['name']


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ['metric_name', 'value', 'unit', 'browser', 'headless', 'timestamp']
    list_filter = ['browser', 'headless', 'metric_name']
