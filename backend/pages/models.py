from django.db import models
import uuid


class PageGenerationTask(models.Model):
    """Represents a batch task to generate multiple pages"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    base_name = models.CharField(max_length=100, help_text="Base name for generated pages")
    count = models.PositiveIntegerField(help_text="Number of pages to generate")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Metrics for efficiency testing
    total_time_seconds = models.FloatField(null=True, blank=True)
    avg_time_per_page = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.base_name} ({self.count} pages) - {self.status}"


class GeneratedPage(models.Model):
    """Individual generated page record"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('creating', 'Creating'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(PageGenerationTask, on_delete=models.CASCADE, related_name='pages')
    name = models.CharField(max_length=150)
    sequence_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Simulated page URL (for testing purposes)
    page_url = models.URLField(blank=True)

    # Timing metrics
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['task', 'sequence_number']

    def __str__(self):
        return f"{self.name} - {self.status}"


class PerformanceMetric(models.Model):
    """Store Selenium performance metrics for analysis"""
    task = models.ForeignKey(PageGenerationTask, on_delete=models.CASCADE, related_name='metrics')
    timestamp = models.DateTimeField(auto_now_add=True)

    # Performance data
    metric_name = models.CharField(max_length=100)
    value = models.FloatField()
    unit = models.CharField(max_length=20, default='seconds')

    # Context
    browser = models.CharField(max_length=50, default='chrome')
    headless = models.BooleanField(default=True)
    parallel_workers = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.metric_name}: {self.value} {self.unit}"
