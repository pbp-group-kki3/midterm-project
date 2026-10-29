import math
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Article(models.Model):
    TOPIC_CHOICES = [
        ('food_waste', 'Food waste'),
        ('packaging', 'Packaging'),
        ('recycling', 'Recycling'),
        ('carbon_footprints', 'Carbon footprints'),
        ('sustainable_shopping', 'Sustainable shopping'),
        ('nutrition_labels', 'Nutrition labels'),
        ('seasonal_food', 'Seasonal food'),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    summary = models.TextField()
    body = models.TextField()
    topic = models.CharField(max_length=30, choices=TOPIC_CHOICES)
    cover_url = models.URLField(max_length=500)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles')
    published_at = models.DateTimeField(default=timezone.now)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title

    @property
    def read_time(self):
        """Calculates estimated reading time in minutes (assumes ~200 wpm)."""
        word_count = len(self.body.split())
        return max(1, math.ceil(word_count / 200))


class ArticleComment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.user.username} on {self.article.title}"