from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserChangeForm
from django.db.models import Count
from django.http import Http404  
from .models import Post, Category, Comment
from .forms import PostForm, CommentForm, UserProfileForm 

User = get_user_model()

POSTS_PER_PAGE = 10


def paginate_posts(request, queryset, per_page=POSTS_PER_PAGE):
    """Универсальная функция пагинации"""
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


def annotate_comments_count(queryset):
    """Добавляет количество комментариев к queryset"""
    return queryset.annotate(comment_count=Count('comments'))


def get_post_queryset(with_comments_count=False):
    """Базовый queryset для опубликованных постов"""
    now = timezone.now()
    queryset = Post.objects.select_related(
        'category', 'author', 'location'
    ).filter(
        is_published=True,
        pub_date__lte=now,
        category__is_published=True
    )
    if with_comments_count:
        queryset = annotate_comments_count(queryset)
    return queryset


def index(request):
    queryset = get_post_queryset(with_comments_count=True)
    post_list = queryset.order_by('-pub_date')
    page_obj = paginate_posts(request, post_list)  
    return render(request, 'blog/index.html', {'page_obj': page_obj})


def post_detail(request, post_id):
    """Страница отдельной публикации с комментариями"""
    now = timezone.now()
    post = get_object_or_404(
        Post.objects.select_related('category', 'author', 'location'),
        id=post_id
    )

    if post.category:
        is_category_published = post.category.is_published
    else:
        is_category_published = True

    if (
        not post.is_published
        or post.pub_date > now
        or not is_category_published
    ):
        if request.user != post.author:
            raise Http404("Пост не найден")
    comments = post.comments.all()
    form = CommentForm()  
    context = {
        'post': post,
        'comments': comments,
        'form': form, 
    }
    return render(request, 'blog/detail.html', context)


def category_posts(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug, is_published=True)
    post_list = get_post_queryset(with_comments_count=True).filter(
        category=category
    ).order_by('-pub_date')
    page_obj = paginate_posts(request, post_list)  
    return render(request, 'blog/category.html', {'category': category, 'page_obj': page_obj})


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    
    if request.user == profile_user:
        post_list = Post.objects.select_related(
            'category', 'author', 'location'
        ).filter(author=profile_user)
        post_list = annotate_comments_count(post_list)  
        post_list = post_list.order_by('-pub_date')
    else:
        post_list = get_post_queryset(with_comments_count=True).filter(
            author=profile_user
        ).order_by('-pub_date')
    
    page_obj = paginate_posts(request, post_list)  
    context = {'profile': profile_user, 'page_obj': page_obj}
    return render(request, 'blog/profile.html', context)


@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)  # ← используем форму из forms.py
        if form.is_valid():
            form.save()
            return redirect('blog:profile', username=request.user.username)
    else:
        form = UserProfileForm(instance=request.user)
    
    context = {'form': form}
    return render(request, 'blog/user.html', context)


@login_required
def post_create(request):
    """Создание новой публикации"""
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('blog:profile', username=request.user.username)
    else:
        form = PostForm()
    context = {'form': form}
    return render(request, 'blog/create.html', context)


@login_required
def post_edit(request, post_id):
    """Редактирование публикации"""
    post = get_object_or_404(Post, id=post_id)
    if post.author != request.user:
        return redirect('blog:post_detail', post_id=post_id)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            return redirect('blog:post_detail', post_id=post_id)
    else:
        form = PostForm(instance=post)
    context = {'form': form}
    return render(request, 'blog/create.html', context)


@login_required
def post_delete(request, post_id):
    """Удаление публикации"""
    post = get_object_or_404(Post, id=post_id)
    if post.author != request.user:
        return redirect('blog:post_detail', post_id=post_id)
    if request.method == 'POST':
        post.delete()
        return redirect('blog:profile', username=request.user.username)
    context = {'post': post}
    return render(request, 'blog/confirm_delete.html', context)


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            return redirect('blog:post_detail', post_id=post_id)
    else:
        form = CommentForm()
    
    comments = post.comments.all()
    context = {
        'post': post,
        'comments': comments,
        'form': form,
    }
    return render(request, 'blog/detail.html', context)


@login_required
def edit_comment(request, post_id, comment_id):
    """Редактирование комментария"""
    comment = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    if comment.author != request.user:
        return redirect('blog:post_detail', post_id=post_id)
    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            return redirect('blog:post_detail', post_id=post_id)
    else:
        form = CommentForm(instance=comment)
    context = {
        'form': form,
        'comment': comment,
    }
    return render(request, 'blog/comment.html', context)


@login_required
def delete_comment(request, post_id, comment_id):
    """Удаление комментария"""
    comment = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    if comment.author != request.user:
        return redirect('blog:post_detail', post_id=post_id)
    # Обработка POST-запроса на удаление
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', post_id=post_id)
    context = {
        'comment': comment,
        'post_id': post_id,
    }
    return render(request, 'blog/comment.html', context)


@login_required
def confirm_delete_comment(request, post_id, comment_id):
    """Подтверждение удаления комментария (POST запрос)"""
    comment = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    if comment.author != request.user:
        return redirect('blog:post_detail', id=post_id)
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', id=post_id)
    return render(request, 'blog/comment.html', {'comment': comment})
