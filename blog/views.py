from django.shortcuts import render
from django.db.models import Q
from .models import Article

def blog_list(request):
    search_query = request.GET.get('q', '').strip()
    selected_topic = request.GET.get('topic', '').strip()

    # Base queryset for published articles
    articles = Article.objects.filter(is_published=True)

    # Apply search filter across title, summary, and body
    if search_query:
        articles = articles.filter(
            Q(title__icontains=search_query) |
            Q(summary__icontains=search_query) |
            Q(body__icontains=search_query)
        )

    # Apply topic filter
    if selected_topic:
        articles = articles.filter(topic=selected_topic)

    # Featured article: pick the latest published article matching current filters
    featured_article = articles.first()

    # Latest articles: remaining articles excluding the featured one
    latest_articles = articles.exclude(id=featured_article.id) if featured_article else []

    # If user is logged in, fetch their articles
    user_articles = []
    if request.user.is_authenticated:
        user_articles = Article.objects.filter(author=request.user)

    context = {
        'featured_article': featured_article,
        'latest_articles': latest_articles,
        'user_articles': user_articles,
        'selected_topic': selected_topic,
        'search_query': search_query,
        'topics': Article.TOPIC_CHOICES,
    }

    return render(request, 'blog.html', context)