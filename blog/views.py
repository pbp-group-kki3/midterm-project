from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import ArticleCommentForm, ArticleForm
from .models import Article, ArticleComment, SavedArticle
from .services import remove_saved_article, save_article_snapshot


# Use one response contract for Blog's asynchronous form submissions.
def is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


# Keep normal navigation and AJAX authentication failures understandable.
def login_response(request):
    login_url = redirect_to_login(
        request.get_full_path(),
        login_url=reverse("login"),
    ).url

    if is_ajax(request):
        return JsonResponse(
            {"ok": False, "message": "Please log in to continue.", "login_url": login_url},
            status=401,
        )

    return redirect(login_url)


# Return useful errors without revealing private article content.
def action_error(request, message, status=400, errors=None):
    if is_ajax(request):
        return JsonResponse(
            {"ok": False, "message": message, "errors": errors or {}},
            status=status,
        )

    return render(
        request,
        "blog_action_error.html",
        {"error_message": message},
        status=status,
    )


# Load the complete visible discussion without repeated author and like queries.
def article_comments(article):
    return (
        article.comments.filter(parent__isnull=True)
        .select_related("user")
        .prefetch_related("likes", "replies__user", "replies__likes")
        .order_by("-created_at")
    )


# Successful navigation uses Django messages, which the global toast reads.
def navigation_success(request, message, destination):
    messages.success(request, message)

    if is_ajax(request):
        return JsonResponse({"ok": True, "redirect_url": destination})

    return redirect(destination)


@require_GET
def blog_list(request):
    q = request.GET.get("q", "").strip()
    topic = request.GET.get("topic", "")

    articles = Article.objects.filter(is_published=True).select_related("author").order_by("-published_at")

    if q:
        articles = articles.filter(Q(title__icontains=q) | Q(summary__icontains=q))
    if topic:
        articles = articles.filter(topic=topic)

    featured_article = articles.first()
    latest_articles = articles.exclude(pk=featured_article.pk) if featured_article else articles

    user_articles = Article.objects.none()
    if request.user.is_authenticated:
        user_articles = Article.objects.filter(author=request.user).order_by("-published_at")

    return render(request, "blog.html", {
        "featured_article": featured_article,
        "latest_articles": latest_articles,
        "user_articles": user_articles,
        "topics": Article.TOPIC_CHOICES,
        "current_topic": topic,
        "q": q,
    })


@never_cache
@require_http_methods(["GET", "POST"])
def article_detail(request, slug):
    article = get_object_or_404(Article.objects.select_related("author"), slug=slug, is_published=True)

    if request.method == "POST":
        if not request.user.is_authenticated:
            return login_response(request)

        action = request.POST.get("action")

        if action == "save_article":
            desired = request.POST.get("saved")

            if desired not in {"0", "1"}:
                return action_error(request, "The save request is invalid.")

            if desired == "1":
                save_article_snapshot(article, request.user)
                message = "Article saved."
            else:
                record = SavedArticle.objects.filter(user=request.user, article=article).first()
                if record:
                    remove_saved_article(record)
                else:
                    article.saved_by.remove(request.user)
                message = "Article removed from Saved."

            if is_ajax(request):
                return JsonResponse({"ok": True, "saved": desired == "1", "message": message})

            messages.success(request, message)
            return redirect(article.get_absolute_url())

        if action == "comment":
            form = ArticleCommentForm(request.POST)

            if not form.is_valid():
                return action_error(
                    request,
                    "Please check your comment.",
                    errors=form.errors.get_json_data(),
                )

            parent = None
            parent_id = form.cleaned_data["parent_id"]

            if parent_id:
                parent = ArticleComment.objects.filter(
                    pk=parent_id,
                    article=article,
                    parent__isnull=True,
                ).first()

                if parent is None:
                    return action_error(request, "That comment is unavailable for replies.")

            ArticleComment.objects.create(
                user=request.user,
                article=article,
                text=form.cleaned_data["text"],
                parent=parent,
            )
            message = "Reply posted." if parent else "Comment posted."

        elif action == "like_comment":
            comment_id = request.POST.get("comment_id", "")

            if not comment_id.isascii() or not comment_id.isdigit():
                return action_error(request, "That comment is unavailable.", status=404)

            comment = ArticleComment.objects.filter(pk=comment_id, article=article).first()
            if comment is None:
                return action_error(request, "That comment is unavailable.", status=404)

            desired = request.POST.get("liked")
            if desired not in {"0", "1"}:
                return action_error(request, "The like request is invalid.")

            if desired == "1":
                comment.likes.add(request.user)
            else:
                comment.likes.remove(request.user)

            message = "Comment like updated."
        else:
            return action_error(request, "Unknown article action.")

        if is_ajax(request):
            html = render_to_string(
                "blog/components/article_comments.html",
                {
                    "article": article,
                    "comments": article_comments(article),
                    "comment_count": article.comments.count(),
                    "comment_action_url": article.get_absolute_url(),
                },
                request=request,
            )
            return JsonResponse({"ok": True, "comments_html": html, "message": message})

        messages.success(request, message)
        return redirect(article.get_absolute_url())

    saved = (
        SavedArticle.objects.filter(user=request.user, article=article).exists()
        if request.user.is_authenticated else False
    )

    return render(request, "article_detail.html", {
        "article": article,
        "comments": article_comments(article),
        "comment_count": article.comments.count(),
        "comment_action_url": article.get_absolute_url(),
        "is_saved": saved,
        "save_url": article.get_absolute_url(),
        "viewing_saved": False,
        "can_edit": request.user.is_authenticated and request.user.pk == article.author_id,
        "can_delete": request.user.is_authenticated and (
            request.user.pk == article.author_id or request.user.is_staff
        ),
        "back_url": reverse("blog:blog_list"),
        "back_label": "Back to Blog",
    })


@never_cache
@require_GET
def saved_article_detail(request, pk):
    if not request.user.is_authenticated:
        return login_response(request)

    record = get_object_or_404(
        SavedArticle.objects.select_related("article"),
        pk=pk,
        user=request.user,
    )
    data = record.snapshot_data

    article = SimpleNamespace(
        title=data.get("title", "Saved article"),
        summary=data.get("summary", ""),
        body=data.get("body", ""),
        author=SimpleNamespace(username=data.get("author_name", "Unknown author")),
        published_at=parse_datetime(data.get("published_at", "")),
        cover_image=record.cover_image,
        get_topic_display=lambda: data.get("topic_label", ""),
        get_read_time=lambda: data.get("read_time", 1),
    )

    source = record.article if record.article and record.article.is_published else None

    return render(request, "article_detail.html", {
        "article": article,
        "comments": article_comments(source) if source else [],
        "comment_count": source.comments.count() if source else 0,
        "comments_available": source is not None,
        "comment_action_url": source.get_absolute_url() if source else "",
        "is_saved": True,
        "save_url": reverse("blog:saved_article_remove", args=[record.pk]),
        "viewing_saved": True,
        "can_edit": False,
        "can_delete": False,
        "back_url": reverse("profile_saved") + "?category=article",
        "back_label": "Back to Saved",
    })


@never_cache
@require_POST
def saved_article_remove(request, pk):
    if not request.user.is_authenticated:
        return login_response(request)

    record = get_object_or_404(SavedArticle, pk=pk, user=request.user)
    remove_saved_article(record)
    destination = reverse("profile_saved") + "?category=article"

    if request.POST.get("return_to_saved") == "1":
        return navigation_success(request, "Article removed from Saved.", destination)

    if is_ajax(request):
        return JsonResponse({"ok": True, "message": "Article removed from Saved."})

    messages.success(request, "Article removed from Saved.")
    return redirect(destination)


@require_POST
def article_delete(request, slug):
    if not request.user.is_authenticated:
        return login_response(request)

    article = get_object_or_404(Article, slug=slug)

    if request.user.pk != article.author_id and not request.user.is_staff:
        return action_error(request, "You do not have permission to delete this article.", status=403)

    article.delete()
    return navigation_success(
        request,
        "Article deleted.",
        reverse("blog:blog_list"),
    )


@require_http_methods(["GET", "POST"])
def article_create(request):
    if not request.user.is_authenticated:
        return login_response(request)

    form = ArticleForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.is_published = True
            article.save()
            return navigation_success(request, "Article published.", article.get_absolute_url())

        if is_ajax(request):
            return action_error(request, "Please check the article fields.", errors=form.errors.get_json_data())

    return render(request, "article_form.html", {
        "form": form,
        "action": "Create",
        "subtitle": "Share an article about food or sustainability.",
    })


@require_http_methods(["GET", "POST"])
def article_edit(request, slug):
    if not request.user.is_authenticated:
        return login_response(request)

    article = get_object_or_404(Article, slug=slug)

    if request.user.pk != article.author_id:
        return action_error(request, "Only the author can edit this article.", status=403)

    form = ArticleForm(
        request.POST or None,
        request.FILES or None,
        instance=article,
    )

    if request.method == "POST":
        if form.is_valid():
            form.save()
            return navigation_success(request, "Article updated.", article.get_absolute_url())

        if is_ajax(request):
            return action_error(request, "Please check the article fields.", errors=form.errors.get_json_data())

    return render(request, "article_form.html", {
        "form": form,
        "action": "Edit",
        "subtitle": "Update your article.",
    })