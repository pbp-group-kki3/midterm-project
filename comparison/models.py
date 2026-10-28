from django.db import models
from django.conf import settings

# Create your models here.
class SavedComparison(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_comparisons",
    )
    name = models.CharField(max_length=150)
    notes = models.TextField(blank=True, max_length=2000)
    barcodes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name