from django.db import models
from django.conf import settings # to pint to project's User model

# Create your models here.

# product saved - favorited
class FavoriteProduct(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_products",
    )                                                         
    barcode = models.CharField(max_length=32)
    product_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:                                               
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "barcode"],
                name="unique_favorite_per_user",
            ),
        ]

    def __str__(self):                                        
        return f"{self.user} - {self.product_name or self.barcode}"

class ViewHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="view_history",
    )
    barcode = models.CharField(max_length=32)
    product_name = models.CharField(max_length=255, blank=True)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["viewed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user","barcode"],
                name="unique_history_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user} viewed {self.product_name or self.barcode}"