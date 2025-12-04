from rest_framework import serializers
from .models import PageGenerationTask, GeneratedPage, PerformanceMetric


class GeneratedPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedPage
        fields = ['id', 'name', 'sequence_number', 'status', 'page_url',
                  'start_time', 'end_time', 'duration_seconds', 'error_message']


class PageGenerationTaskSerializer(serializers.ModelSerializer):
    pages = GeneratedPageSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = PageGenerationTask
        fields = ['id', 'base_name', 'count', 'status', 'created_at',
                  'started_at', 'completed_at', 'total_time_seconds',
                  'avg_time_per_page', 'pages', 'progress']

    def get_progress(self, obj):
        total = obj.pages.count()
        if total == 0:
            return 0
        completed = obj.pages.filter(status__in=['success', 'failed']).count()
        return round((completed / total) * 100, 1)


class CreateTaskSerializer(serializers.Serializer):
    base_name = serializers.CharField(max_length=100)
    count = serializers.IntegerField(min_value=1, max_value=100)

    def validate_base_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Base name cannot be empty")
        return value.strip()


class PerformanceMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceMetric
        fields = ['id', 'task', 'timestamp', 'metric_name', 'value',
                  'unit', 'browser', 'headless', 'parallel_workers']


class EfficiencyReportSerializer(serializers.Serializer):
    """Serializer for efficiency analysis report"""
    total_tasks = serializers.IntegerField()
    total_pages_generated = serializers.IntegerField()
    avg_time_per_page = serializers.FloatField()
    fastest_page = serializers.FloatField()
    slowest_page = serializers.FloatField()
    success_rate = serializers.FloatField()
    metrics_by_browser = serializers.DictField()
