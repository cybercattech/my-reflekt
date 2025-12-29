from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count
import json
from .models import Post, Category


# =============================================================================
# Public Views
# =============================================================================

def post_list(request):
    """List all published blog posts."""
    posts = Post.objects.filter(status='published').order_by('-published_at')
    categories = Category.objects.all()

    paginator = Paginator(posts, 9)  # 3x3 grid
    page = request.GET.get('page')
    posts = paginator.get_page(page)

    return render(request, 'blog/post_list.html', {
        'posts': posts,
        'categories': categories,
    })


def category_posts(request, slug):
    """List posts in a specific category."""
    category = get_object_or_404(Category, slug=slug)
    posts = Post.objects.filter(
        status='published',
        category=category
    ).order_by('-published_at')
    categories = Category.objects.all()

    paginator = Paginator(posts, 9)
    page = request.GET.get('page')
    posts = paginator.get_page(page)

    return render(request, 'blog/post_list.html', {
        'posts': posts,
        'categories': categories,
        'current_category': category,
    })


def post_detail(request, slug):
    """View a single blog post."""
    post = get_object_or_404(Post, slug=slug)

    # Only allow viewing published posts (unless staff)
    if post.status != 'published' and not request.user.is_staff:
        return redirect('blog:post_list')

    return render(request, 'blog/post_detail.html', {
        'post': post,
    })


# =============================================================================
# Admin Views
# =============================================================================

@staff_member_required
def admin_post_list(request):
    """Admin view to list all posts."""
    posts = Post.objects.all().order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        posts = posts.filter(status=status_filter)

    return render(request, 'admin/blog/post_list.html', {
        'posts': posts,
        'status_filter': status_filter,
        'title': 'Blog Posts',
        'active_page': 'blog',
    })


@staff_member_required
def admin_post_create(request):
    """Admin view to create a new post."""
    categories = Category.objects.all()

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        excerpt = request.POST.get('excerpt', '').strip()
        featured_image = request.POST.get('featured_image', '').strip()
        status = request.POST.get('status', 'draft')
        category_id = request.POST.get('category', '')

        if not title or not content:
            messages.error(request, 'Title and content are required.')
            return render(request, 'admin/blog/post_form.html', {
                'title': 'New Post',
                'active_page': 'blog',
                'form_data': request.POST,
                'categories': categories,
            })

        category = None
        if category_id:
            try:
                category = Category.objects.get(pk=category_id)
            except Category.DoesNotExist:
                pass

        post = Post.objects.create(
            title=title,
            content=content,
            excerpt=excerpt,
            featured_image=featured_image,
            status=status,
            category=category,
            author=request.user,
        )

        messages.success(request, f'Post "{post.title}" created successfully!')
        return redirect('blog:admin_list')

    return render(request, 'admin/blog/post_editor.html', {
        'title': 'New Post',
        'active_page': 'blog',
        'categories': categories,
    })


@staff_member_required
def admin_post_edit(request, pk):
    """Admin view to edit an existing post."""
    post = get_object_or_404(Post, pk=pk)
    categories = Category.objects.all()

    if request.method == 'POST':
        post.title = request.POST.get('title', '').strip()
        post.content = request.POST.get('content', '').strip()
        post.excerpt = request.POST.get('excerpt', '').strip()
        post.featured_image = request.POST.get('featured_image', '').strip()
        post.status = request.POST.get('status', 'draft')
        category_id = request.POST.get('category', '')

        if category_id:
            try:
                post.category = Category.objects.get(pk=category_id)
            except Category.DoesNotExist:
                post.category = None
        else:
            post.category = None

        if not post.title or not post.content:
            messages.error(request, 'Title and content are required.')
            return render(request, 'admin/blog/post_editor.html', {
                'title': f'Edit: {post.title}',
                'active_page': 'blog',
                'post': post,
                'categories': categories,
            })

        post.save()
        messages.success(request, f'Post "{post.title}" updated successfully!')
        return redirect('blog:admin_list')

    return render(request, 'admin/blog/post_editor.html', {
        'title': f'Edit: {post.title}',
        'active_page': 'blog',
        'post': post,
        'categories': categories,
    })


@staff_member_required
def admin_post_delete(request, pk):
    """Admin view to delete a post."""
    post = get_object_or_404(Post, pk=pk)

    if request.method == 'POST':
        title = post.title
        post.delete()
        messages.success(request, f'Post "{title}" deleted successfully!')
        return redirect('blog:admin_list')

    return render(request, 'admin/blog/post_confirm_delete.html', {
        'title': f'Delete: {post.title}',
        'active_page': 'blog',
        'post': post,
    })


@staff_member_required
def admin_post_toggle_status(request, pk):
    """Toggle post status between draft and published."""
    post = get_object_or_404(Post, pk=pk)

    if post.status == 'published':
        post.status = 'draft'
        post.published_at = None
    else:
        post.status = 'published'

    post.save()
    messages.success(request, f'Post "{post.title}" is now {post.status}.')
    return redirect('blog:admin_list')


@staff_member_required
@require_POST
def admin_post_autosave(request):
    """Auto-save endpoint for blog posts."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    post_id = data.get('post_id')
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    excerpt = data.get('excerpt', '').strip()
    featured_image = data.get('featured_image', '').strip()
    category_id = data.get('category')

    # Get or create category
    category = None
    if category_id:
        try:
            category = Category.objects.get(pk=category_id)
        except Category.DoesNotExist:
            pass

    if post_id:
        # Update existing post
        try:
            post = Post.objects.get(pk=post_id)
            post.title = title or post.title
            post.content = content
            post.excerpt = excerpt
            post.featured_image = featured_image
            post.category = category
            post.save()
            return JsonResponse({
                'success': True,
                'post_id': post.id,
                'message': 'Saved',
                'updated_at': post.updated_at.isoformat()
            })
        except Post.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Post not found'}, status=404)
    else:
        # Create new post (as draft)
        if not title:
            title = 'Untitled'
        post = Post.objects.create(
            title=title,
            content=content,
            excerpt=excerpt,
            featured_image=featured_image,
            category=category,
            status='draft',
            author=request.user,
        )
        return JsonResponse({
            'success': True,
            'post_id': post.id,
            'message': 'Draft created',
            'updated_at': post.updated_at.isoformat()
        })


@staff_member_required
def admin_category_list(request):
    """Admin view to manage categories."""
    categories = Category.objects.annotate(
        post_count=Count('posts')
    ).order_by('name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', '#06c8ea').strip()

        if name:
            Category.objects.create(name=name, color=color)
            messages.success(request, f'Category "{name}" created.')
        return redirect('blog:admin_categories')

    return render(request, 'admin/blog/category_list.html', {
        'categories': categories,
        'title': 'Categories',
        'active_page': 'blog',
    })


@staff_member_required
def admin_category_delete(request, pk):
    """Delete a category."""
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" deleted.')
    return redirect('blog:admin_categories')
