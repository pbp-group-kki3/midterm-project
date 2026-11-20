from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
)
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Article, ArticleComment, SavedArticle
from .serializers import (
    ArticleCommentSerializer,
    ArticleDetailSerializer,
    ArticleListSerializer,
    ArticleWriteSerializer,
    SavedArticleSerializer,
)
from .services import remove_saved_article, save_article_snapshot


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if str(value).lower() in {"1", "true", "yes"}:
        return True
    if str(value).lower() in {"0", "false", "no"}:
        return False
    return None


# =====================================================================
# BLOG ARTICLE ENDPOINTS
# =====================================================================


@api_view(["GET", "POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def api_article_list_create(request):
    if request.method == "GET":
        q = request.GET.get("q", "").strip()
        topic = request.GET.get("topic", "").strip()
        mine = _parse_bool(request.GET.get("mine"))

        if mine:
            if not request.user.is_authenticated:
                return Response(
                    {"ok": False, "message": "Authentication required."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            articles = Article.objects.filter(author=request.user).select_related("author")
        else:
            articles = Article.objects.filter(is_published=True).select_related("author")

        if q:
            articles = articles.filter(Q(title__icontains=q) | Q(summary__icontains=q))
        if topic:
            articles = articles.filter(topic=topic)

        articles = articles.order_by("-published_at")
        serializer = ArticleListSerializer(articles, many=True, context={"request": request})

        return Response(
            {
                "ok": True,
                "topics": [{"value": v, "label": l} for v, l in Article.TOPIC_CHOICES],
                "articles": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    # POST: Create article
    if not request.user.is_authenticated:
        return Response(
            {"ok": False, "message": "Please log in to publish an article."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    serializer = ArticleWriteSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return Response(
            {
                "ok": False,
                "message": "Please check the article fields.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    article = serializer.save(author=request.user, is_published=True)
    detail_data = ArticleDetailSerializer(article, context={"request": request}).data

    return Response(
        {
            "ok": True,
            "message": "Article published.",
            "article": detail_data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@authentication_classes([CsrfExemptSessionAuthentication])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def api_article_detail(request, slug):
    article = get_object_or_404(Article.objects.select_related("author"), slug=slug)

    if not article.is_published and (
        not request.user.is_authenticated or request.user.pk != article.author_id
    ):
        return Response(
            {"ok": False, "message": "Article not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        serializer = ArticleDetailSerializer(article, context={"request": request})
        return Response({"ok": True, "article": serializer.data}, status=status.HTTP_200_OK)

    if not request.user.is_authenticated:
        return Response(
            {"ok": False, "message": "Please log in to continue."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if request.method in {"PUT", "PATCH"}:
        if request.user.pk != article.author_id:
            return Response(
                {"ok": False, "message": "Only the author can edit this article."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ArticleWriteSerializer(
            article,
            data=request.data,
            partial=(request.method == "PATCH"),
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(
                {
                    "ok": False,
                    "message": "Please check the article fields.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_article = serializer.save()
        detail_data = ArticleDetailSerializer(updated_article, context={"request": request}).data
        return Response(
            {
                "ok": True,
                "message": "Article updated.",
                "article": detail_data,
            },
            status=status.HTTP_200_OK,
        )

    # DELETE
    if request.user.pk != article.author_id and not request.user.is_staff:
        return Response(
            {"ok": False, "message": "You do not have permission to delete this article."},
            status=status.HTTP_403_FORBIDDEN,
        )

    article.delete()
    return Response(
        {"ok": True, "message": "Article deleted."},
        status=status.HTTP_200_OK,
    )


# =====================================================================
# COMMENTS & LIKES ENDPOINTS
# =====================================================================


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def api_article_comment_create(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)

    payload = request.data.copy()
    if "parent_id" in payload and "parent" not in payload:
        payload["parent"] = payload.get("parent_id")

    serializer = ArticleCommentSerializer(
        data=payload,
        context={"request": request, "article": article},
    )
    if not serializer.is_valid():
        return Response(
            {
                "ok": False,
                "message": "Please check your comment.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    comment = serializer.save(user=request.user, article=article)
    message = "Reply posted." if comment.parent_id else "Comment posted."

    return Response(
        {
            "ok": True,
            "message": message,
            "comment": ArticleCommentSerializer(comment, context={"request": request}).data,
            "comment_count": article.comments.count(),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def api_comment_like(request, slug, comment_id):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    comment = get_object_or_404(ArticleComment, pk=comment_id, article=article)

    desired = _parse_bool(request.data.get("liked"))
    if desired is None:
        desired = not comment.likes.filter(pk=request.user.pk).exists()

    if desired:
        comment.likes.add(request.user)
    else:
        comment.likes.remove(request.user)

    return Response(
        {
            "ok": True,
            "is_liked": desired,
            "like_count": comment.likes.count(),
            "message": "Comment like updated.",
        },
        status=status.HTTP_200_OK,
    )


# =====================================================================
# SAVED ARTICLES & SNAPSHOTS (REUSING services.py)
# =====================================================================


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def api_article_save_toggle(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)

    desired = _parse_bool(request.data.get("saved"))
    existing_record = SavedArticle.objects.filter(user=request.user, article=article).first()

    if desired is None:
        desired = existing_record is None

    if desired:
        record = save_article_snapshot(article, request.user)
        return Response(
            {
                "ok": True,
                "is_saved": True,
                "saved_id": record.pk,
                "message": "Article saved.",
            },
            status=status.HTTP_200_OK,
        )

    if existing_record:
        remove_saved_article(existing_record)
    else:
        article.saved_by.remove(request.user)

    return Response(
        {
            "ok": True,
            "is_saved": False,
            "saved_id": None,
            "message": "Article removed from Saved.",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def api_saved_list(request):
    records = SavedArticle.objects.filter(user=request.user).select_related("article")
    serializer = SavedArticleSerializer(records, many=True, context={"request": request})
    return Response(
        {
            "ok": True,
            "saved_articles": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "DELETE"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def api_saved_detail_remove(request, pk):
    record = get_object_or_404(
        SavedArticle.objects.select_related("article"),
        pk=pk,
        user=request.user,
    )

    if request.method == "GET":
        serializer = SavedArticleSerializer(record, context={"request": request})
        return Response(
            {
                "ok": True,
                "saved_article": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    remove_saved_article(record)
    return Response(
        {
            "ok": True,
            "message": "Article removed from Saved.",
        },
        status=status.HTTP_200_OK,
    )