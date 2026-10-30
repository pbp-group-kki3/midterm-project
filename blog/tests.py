from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Article, ArticleComment, SavedArticle
from .services import save_article_snapshot
from .templatetags.blog_tags import link_barcodes


class BlogIntegrationTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.media_settings = override_settings(MEDIA_ROOT=self.media.name)
        self.media_settings.enable()
        self.addCleanup(self.media.cleanup)
        self.addCleanup(self.media_settings.disable)

        User = get_user_model()
        self.author = User.objects.create_user("blog-author")
        self.reader = User.objects.create_user("blog-reader")
        self.other = User.objects.create_user("blog-other")
        self.article = Article.objects.create(
            title="Reading food labels",
            summary="A short introduction.",
            body="Original article body.",
            topic="nutrition_labels",
            author=self.author,
            is_published=True,
        )
        self.client.force_login(self.reader)
        self.detail_url = self.article.get_absolute_url()
        self.ajax = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

    def save_article(self):
        return self.client.post(
            self.detail_url,
            {"action": "save_article", "saved": "1"},
            **self.ajax,
        )

    # Saving is idempotent and preserves the first saved version.
    def test_save_creates_one_snapshot_and_does_not_refresh_it(self):
        self.assertEqual(self.save_article().status_code, 200)
        record = SavedArticle.objects.get(user=self.reader, article=self.article)

        self.article.body = "Edited live body."
        self.article.save()

        self.assertEqual(self.save_article().status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.snapshot_data["body"], "Original article body.")
        self.assertEqual(SavedArticle.objects.count(), 1)
        self.assertTrue(self.article.saved_by.filter(pk=self.reader.pk).exists())

    def test_snapshot_survives_source_deletion(self):
        record = save_article_snapshot(self.article, self.reader)
        self.article.delete()

        record.refresh_from_db()
        self.assertIsNone(record.article_id)

        response = self.client.get(reverse("blog:saved_article_detail", args=[record.pk]))
        self.assertContains(response, "Original article body.")
        self.assertContains(response, "Back to Saved")
        self.assertNotContains(response, "Delete article")

    def test_profile_articles_filter_displays_saved_snapshot(self):
        self.save_article()
        response = self.client.get(reverse("profile_saved"), {"category": "article"})
        self.assertContains(response, self.article.title)
        self.assertNotContains(response, "Article bookmarks are not available yet.")

    def test_unsaving_removes_only_the_readers_snapshot(self):
        first = save_article_snapshot(self.article, self.reader)
        second = save_article_snapshot(self.article, self.other)

        response = self.client.post(
            reverse("blog:saved_article_remove", args=[first.pk]),
            **self.ajax,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SavedArticle.objects.filter(pk=first.pk).exists())
        self.assertTrue(SavedArticle.objects.filter(pk=second.pk).exists())
        self.assertTrue(Article.objects.filter(pk=self.article.pk).exists())

    def test_foreign_snapshot_cannot_be_opened_or_removed(self):
        record = save_article_snapshot(self.article, self.other)

        self.assertEqual(
            self.client.get(reverse("blog:saved_article_detail", args=[record.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("blog:saved_article_remove", args=[record.pk]), **self.ajax).status_code,
            404,
        )
        self.assertTrue(SavedArticle.objects.filter(pk=record.pk).exists())

    def test_guest_cannot_save(self):
        response = Client().post(
            self.detail_url,
            {"action": "save_article", "saved": "1"},
            **self.ajax,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(SavedArticle.objects.count(), 0)

    def test_reader_cannot_edit_or_delete_another_authors_article(self):
        edit = self.client.post(
            reverse("blog:article_edit", args=[self.article.slug]),
            {"title": "Unauthorized"},
            **self.ajax,
        )
        delete = self.client.post(
            reverse("blog:article_delete", args=[self.article.slug]),
            **self.ajax,
        )

        self.assertEqual(edit.status_code, 403)
        self.assertEqual(delete.status_code, 403)
        self.assertTrue(Article.objects.filter(pk=self.article.pk).exists())

    def test_reply_and_like_cannot_target_another_article(self):
        other_article = Article.objects.create(
            title="Another article",
            body="Other body",
            summary="Other summary",
            topic="packaging",
            author=self.author,
            is_published=True,
        )
        foreign_comment = ArticleComment.objects.create(
            user=self.other,
            article=other_article,
            text="Not part of the first article.",
        )

        reply = self.client.post(
            self.detail_url,
            {"action": "comment", "text": "Invalid reply", "parent_id": foreign_comment.pk},
            **self.ajax,
        )
        like = self.client.post(
            self.detail_url,
            {"action": "like_comment", "comment_id": foreign_comment.pk, "liked": "1"},
            **self.ajax,
        )

        self.assertEqual(reply.status_code, 400)
        self.assertEqual(like.status_code, 404)
        self.assertEqual(ArticleComment.objects.count(), 1)
        self.assertFalse(foreign_comment.likes.exists())

    def test_comment_ajax_returns_updated_discussion(self):
        response = self.client.post(
            self.detail_url,
            {"action": "comment", "text": "Useful article."},
            **self.ajax,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Useful article.", response.json()["comments_html"])
        self.assertEqual(self.article.comments.count(), 1)

    def test_blank_comment_is_rejected(self):
        response = self.client.post(
            self.detail_url,
            {"action": "comment", "text": "   "},
            **self.ajax,
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.article.comments.exists())

    def test_csrf_and_post_requirements_remain_enabled(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reader)

        self.assertEqual(
            client.post(self.detail_url, {"action": "save_article", "saved": "1"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("blog:article_delete", args=[self.article.slug])).status_code,
            405,
        )

    def test_duplicate_titles_receive_distinct_slugs(self):
        second = Article.objects.create(
            title=self.article.title,
            summary="Second",
            body="Second",
            topic="packaging",
            author=self.author,
            is_published=True,
        )
        self.assertNotEqual(second.slug, self.article.slug)

    def test_barcode_links_escape_article_html(self):
        output = link_barcodes('<script>alert(1)</script> 1234567890123')
        self.assertNotIn("<script>", output)
        self.assertIn("&lt;script&gt;", output)
        self.assertIn(reverse("main:product_detail", args=["1234567890123"]), output)

    def test_featured_article_is_not_repeated_in_latest(self):
        response = self.client.get(reverse("blog:blog_list"))
        featured = response.context["featured_article"]
        self.assertNotIn(featured.pk, response.context["latest_articles"].values_list("pk", flat=True))