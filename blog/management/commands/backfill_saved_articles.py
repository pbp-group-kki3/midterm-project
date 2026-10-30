from django.core.management.base import BaseCommand

from blog.models import Article, SavedArticle
from blog.services import save_article_snapshot


class Command(BaseCommand):
    help = "Create missing snapshots for existing article bookmarks."

    def handle(self, *args, **options):
        created = 0

        articles = Article.objects.filter(saved_by__isnull=False).distinct()

        for article in articles.iterator():
            for user in article.saved_by.all():
                if SavedArticle.objects.filter(user=user, article=article).exists():
                    continue

                save_article_snapshot(article, user)
                created += 1

        self.stdout.write(
            self.style.SUCCESS(f"Created {created} saved article snapshots.")
        )