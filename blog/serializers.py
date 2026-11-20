from django.contrib.auth import get_user_model
from rest_framework import serializers

from blog.models import Article, ArticleComment, SavedArticle

User = get_user_model()


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]
        read_only_fields = fields

class CommentReplySerializer(serializers.ModelSerializer):
    user = AuthorSerializer(read_only=True)
    like_count = serializers.IntegerField(source="likes.count", read_only=True)
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = ArticleComment
        fields = [
            "id",
            "user",
            "text",
            "created_at",
            "like_count",
            "is_liked",
        ]
        read_only_fields = ["id", "user", "created_at", "like_count", "is_liked"]

    def get_is_liked(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.likes.filter(pk=request.user.pk).exists()


class ArticleCommentSerializer(serializers.ModelSerializer):
    user = AuthorSerializer(read_only=True)
    replies = CommentReplySerializer(many=True, read_only=True)
    like_count = serializers.IntegerField(source="likes.count", read_only=True)
    is_liked = serializers.SerializerMethodField()
    text = serializers.CharField(max_length=2000, trim_whitespace=True)

    class Meta:
        model = ArticleComment
        fields = [
            "id",
            "article",
            "user",
            "parent",
            "text",
            "created_at",
            "like_count",
            "is_liked",
            "replies",
        ]
        read_only_fields = ["id", "article", "user", "created_at", "like_count", "is_liked", "replies"]

    def get_is_liked(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.likes.filter(pk=request.user.pk).exists()

    def validate(self, attrs):
        parent = attrs.get("parent")
        article = self.context.get("article") or getattr(self.instance, "article", None)

        if parent:
            if article and parent.article_id != article.id:
                raise serializers.ValidationError(
                    {"parent": "Parent comment must belong to the same article."}
                )
            if parent.parent_id is not None:
                raise serializers.ValidationError(
                    {"parent": "Replies can only be added to top-level comments."}
                )
        return attrs


class ArticleListSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    topic_label = serializers.CharField(source="get_topic_display", read_only=True)
    read_time = serializers.IntegerField(source="get_read_time", read_only=True)
    comment_count = serializers.IntegerField(source="comments.count", read_only=True)
    is_saved = serializers.SerializerMethodField()
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "summary",
            "topic",
            "topic_label",
            "cover_image",
            "author",
            "published_at",
            "is_published",
            "read_time",
            "comment_count",
            "is_saved",
            "url",
        ]
        read_only_fields = fields

    def get_is_saved(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return SavedArticle.objects.filter(user=request.user, article=obj).exists()


class ArticleDetailSerializer(ArticleListSerializer):
    comments = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta(ArticleListSerializer.Meta):
        fields = ArticleListSerializer.Meta.fields + [
            "body",
            "comments",
            "can_edit",
            "can_delete",
        ]
        read_only_fields = fields

    def get_comments(self, obj):
        top_level_comments = (
            obj.comments.filter(parent__isnull=True)
            .select_related("user")
            .prefetch_related("likes", "replies__user", "replies__likes")
            .order_by("-created_at")
        )
        return ArticleCommentSerializer(
            top_level_comments, many=True, context=self.context
        ).data

    def get_can_edit(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and request.user.pk == obj.author_id)

    def get_can_delete(self, obj):
        request = self.context.get("request")
        return bool(
            request
            and request.user.is_authenticated
            and (request.user.pk == obj.author_id or request.user.is_staff)
        )


class ArticleWriteSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(read_only=True)
    summary = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "summary",
            "body",
            "topic",
            "cover_image",
            "is_published",
        ]


class SavedArticleSerializer(serializers.ModelSerializer):
    article_slug = serializers.SerializerMethodField()
    is_source_available = serializers.SerializerMethodField()

    class Meta:
        model = SavedArticle
        fields = [
            "id",
            "article",
            "article_slug",
            "is_source_available",
            "snapshot_data",
            "cover_image",
            "created_at",
        ]
        read_only_fields = fields

    def get_is_source_available(self, obj):
        return bool(obj.article and obj.article.is_published)

    def get_article_slug(self, obj):
        if obj.article and obj.article.is_published:
            return obj.article.slug
        return None