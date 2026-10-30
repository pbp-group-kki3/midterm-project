from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings
from uuid import uuid4

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

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200)
    summary = models.CharField(max_length=300)
    body = models.TextField()
    topic = models.CharField(max_length=50, choices=TOPIC_CHOICES)
    cover_image = models.ImageField(upload_to='blog/covers/', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles')
    published_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)
    saved_by = models.ManyToManyField(User, related_name='saved_articles', blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            title_slug = slugify(self.title)[:180] or "article"
            self.slug = f"{title_slug}-{uuid4().hex[:12]}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:article_detail', kwargs={'slug': self.slug})

    def get_read_time(self):
        # Calculates read time assuming an average reading speed of 200 words per minute
        word_count = len(self.body.split())
        return max(1, word_count // 200)

    def __str__(self):
        return self.title

class ArticleComment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    likes = models.ManyToManyField(User, related_name='liked_comments', blank=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.article.title}"

# Preserve an owned article snapshot independently of its source article.
class SavedArticle(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="article_snapshots",
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="saved_snapshots",
    )
    snapshot_data = models.JSONField(default=dict)
    cover_image = models.ImageField(
        upload_to="blog/saved_covers/",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "article"],
                name="blog_unique_saved_article",
            ),
        ]

    def __str__(self):
        return self.snapshot_data.get("title", "Saved article")