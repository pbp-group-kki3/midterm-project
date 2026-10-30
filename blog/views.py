from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from .models import Article, ArticleComment
from .forms import ArticleForm

def blog_list(request):
    q = request.GET.get('q', '')
    topic = request.GET.get('topic', '')

    articles = Article.objects.filter(is_published=True).order_by('-published_at')
    
    if q:
        articles = articles.filter(Q(title__icontains=q) | Q(summary__icontains=q))
    if topic:
        articles = articles.filter(topic=topic)

    # Use the first article as the featured piece, and the rest as 'latest'
    featured_article = articles.first()
    latest_articles = articles

    user_articles = []
    if request.user.is_authenticated:
        user_articles = Article.objects.filter(author=request.user).order_by('-published_at')

    context = {
        'featured_article': featured_article,
        'latest_articles': latest_articles,
        'user_articles': user_articles,
        'topics': Article.TOPIC_CHOICES,
        'current_topic': topic,
        'q': q,
    }
    return render(request, 'blog.html', context)

def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
            
        action = request.POST.get('action')
        
        # Handle new comments and replies
        if action == 'comment':
            text = request.POST.get('text')
            parent_id = request.POST.get('parent_id')
            if text:
                parent_comment = ArticleComment.objects.filter(id=parent_id).first() if parent_id else None
                ArticleComment.objects.create(
                    user=request.user,
                    article=article,
                    text=text,
                    parent=parent_comment
                )
                
        # Handle saving the article
        elif action == 'save_article':
            if request.user in article.saved_by.all():
                article.saved_by.remove(request.user)
            else:
                article.saved_by.add(request.user)
                
        # Handle liking a comment
        elif action == 'like_comment':
            comment_id = request.POST.get('comment_id')
            comment = ArticleComment.objects.filter(id=comment_id).first()
            if comment:
                if request.user in comment.likes.all():
                    comment.likes.remove(request.user)
                else:
                    comment.likes.add(request.user)
                    
        return redirect('blog:article_detail', slug=slug)

    # Fetch only top-level comments (replies are accessed via comment.replies.all)
    comments = article.comments.filter(parent__isnull=True).order_by('-created_at')
    
    context = {
        'article': article,
        'comments': comments,
    }
    return render(request, 'article_detail.html', context)

@login_required
def article_delete(request, slug):
    article = get_object_or_404(Article, slug=slug)
    # Check permissions: must be the author or a staff member
    if request.user == article.author or request.user.is_staff:
        if request.method == 'POST':
            article.delete()
            return redirect('blog:blog_list')
    return redirect('blog:article_detail', slug=slug)

@login_required
def article_create(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.is_published = True
            article.save()
            return redirect('blog:article_detail', slug=article.slug)
    else:
        form = ArticleForm()

    context = {
        'form': form,
        'action': 'Create',
        'subtitle': 'Share an article about food or sustainability.'
    }
    return render(request, 'article_form.html', context)

@login_required
def article_edit(request, slug):
    article = get_object_or_404(Article, slug=slug)
    
    # Security check: only the author can edit
    if request.user != article.author:
        return redirect('blog:article_detail', slug=slug)

    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            form.save()
            return redirect('blog:article_detail', slug=article.slug)
    else:
        form = ArticleForm(instance=article)

    context = {
        'form': form,
        'action': 'Edit',
        'subtitle': 'Prototype example input'
    }
    return render(request, 'article_form.html', context)