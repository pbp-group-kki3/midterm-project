import logging
from pathlib import Path
from uuid import uuid4

from django.core.files import File
from django.db import transaction

from .models import Article, SavedArticle


logger = logging.getLogger(__name__)


# File cleanup must not turn an already successful database action into an error.
def delete_snapshot_file(storage, name):
    try:
        storage.delete(name)
    except Exception:
        logger.exception("Could not remove a saved article cover.")


# Create a snapshot once; repeated saves must not refresh its preserved content.
def save_article_snapshot(article, user):
    copied_name = ""
    storage = SavedArticle._meta.get_field("cover_image").storage

    try:
        with transaction.atomic():
            article = Article.objects.select_for_update().select_related("author").get(pk=article.pk)
            record = SavedArticle.objects.filter(user=user, article=article).first()

            if record is None:
                record = SavedArticle(
                    user=user,
                    article=article,
                    snapshot_data={
                        "title": article.title,
                        "summary": article.summary,
                        "body": article.body,
                        "topic": article.topic,
                        "topic_label": article.get_topic_display(),
                        "author_name": article.author.username,
                        "published_at": article.published_at.isoformat(),
                        "read_time": article.get_read_time(),
                    },
                )

                if article.cover_image:
                    extension = Path(article.cover_image.name).suffix.lower()
                    filename = f"{uuid4().hex}{extension}"

                    with article.cover_image.open("rb") as source:
                        record.cover_image.save(filename, File(source), save=False)

                    copied_name = record.cover_image.name

                record.save()

            article.saved_by.add(user)
            return record
    except Exception:
        if copied_name:
            delete_snapshot_file(storage, copied_name)
        raise


# Remove only this user's saved copy and preserve the source article.
def remove_saved_article(record):
    with transaction.atomic():
        record = SavedArticle.objects.select_for_update().get(pk=record.pk)
        article_id = record.article_id
        user_id = record.user_id
        storage = record.cover_image.storage
        filename = record.cover_image.name

        record.delete()

        if article_id:
            article = Article.objects.filter(pk=article_id).first()
            if article:
                article.saved_by.remove(user_id)

        if filename:
            transaction.on_commit(
                lambda: delete_snapshot_file(storage, filename)
            )