"""
Admin views for managing prompt categories and prompts.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.text import slugify

from .models import PromptCategory, Prompt


@staff_member_required
def prompt_category_list(request):
    """List all prompt categories for admin management."""
    categories = PromptCategory.objects.all().order_by('display_order', 'name')

    # Calculate stats
    total_prompts = Prompt.objects.filter(is_active=True).count()

    context = {
        'categories': categories,
        'total_prompts': total_prompts,
        'title': 'Prompt Management',
        'active_page': 'admin_prompts',
    }
    return render(request, 'admin/prompts/category_list.html', context)


@staff_member_required
def prompt_category_create(request):
    """Create a new prompt category."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.POST.get('icon', 'bi-lightbulb')
        color = request.POST.get('color', '#7c3aed')
        image_url = request.POST.get('image_url', '').strip()
        is_default = request.POST.get('is_default') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        display_order = int(request.POST.get('display_order', 0))

        # Generate slug from name
        slug = slugify(name)
        counter = 1
        base_slug = slug
        while PromptCategory.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # If setting as default, unset other defaults
        if is_default:
            PromptCategory.objects.filter(is_default=True).update(is_default=False)

        category = PromptCategory.objects.create(
            name=name,
            slug=slug,
            description=description,
            icon=icon,
            color=color,
            image_url=image_url,
            is_default=is_default,
            is_active=is_active,
            display_order=display_order,
        )

        messages.success(request, f"Category '{category.name}' created. Now add prompts!")
        return redirect('accounts:admin_prompt_prompts', pk=category.pk)

    context = {
        'title': 'Create Category',
        'active_page': 'admin_prompts',
    }
    return render(request, 'admin/prompts/category_form.html', context)


@staff_member_required
def prompt_category_edit(request, pk):
    """Edit an existing prompt category."""
    category = get_object_or_404(PromptCategory, pk=pk)

    if request.method == 'POST':
        category.name = request.POST.get('name', '').strip()
        category.description = request.POST.get('description', '').strip()
        category.icon = request.POST.get('icon', 'bi-lightbulb')
        category.color = request.POST.get('color', '#7c3aed')
        category.image_url = request.POST.get('image_url', '').strip()
        is_default = request.POST.get('is_default') == 'on'
        category.is_active = request.POST.get('is_active') == 'on'
        category.display_order = int(request.POST.get('display_order', 0))

        # If setting as default, unset other defaults
        if is_default and not category.is_default:
            PromptCategory.objects.filter(is_default=True).update(is_default=False)
        category.is_default = is_default

        category.save()

        messages.success(request, f"Category '{category.name}' updated.")
        return redirect('accounts:admin_prompt_list')

    context = {
        'category': category,
        'title': f'Edit: {category.name}',
        'active_page': 'admin_prompts',
    }
    return render(request, 'admin/prompts/category_form.html', context)


@staff_member_required
def prompt_category_delete(request, pk):
    """Delete a prompt category."""
    category = get_object_or_404(PromptCategory, pk=pk)

    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f"Category '{name}' and all its prompts deleted.")
        return redirect('accounts:admin_prompt_list')

    context = {
        'category': category,
        'title': f'Delete: {category.name}',
        'active_page': 'admin_prompts',
    }
    return render(request, 'admin/prompts/category_confirm_delete.html', context)


@staff_member_required
def prompt_prompts(request, pk):
    """Manage prompts within a category."""
    category = get_object_or_404(PromptCategory, pk=pk)
    prompts = category.prompts.all().order_by('day_number')

    context = {
        'category': category,
        'prompts': prompts,
        'title': f'Prompts: {category.name}',
        'active_page': 'admin_prompts',
    }
    return render(request, 'admin/prompts/prompt_list.html', context)


@staff_member_required
@require_POST
def prompt_add(request, pk):
    """Add a new prompt to a category."""
    category = get_object_or_404(PromptCategory, pk=pk)

    text = request.POST.get('text', '').strip()
    day_number = int(request.POST.get('day_number', 1))
    is_active = request.POST.get('is_active') != 'off'

    if not text:
        messages.error(request, "Prompt text is required.")
        return redirect('accounts:admin_prompt_prompts', pk=pk)

    Prompt.objects.create(
        category=category,
        text=text,
        day_number=day_number,
        is_active=is_active,
    )

    messages.success(request, "Prompt added.")
    return redirect('accounts:admin_prompt_prompts', pk=pk)


@staff_member_required
@require_POST
def prompt_edit(request, pk, prompt_pk):
    """Edit an existing prompt."""
    category = get_object_or_404(PromptCategory, pk=pk)
    prompt = get_object_or_404(Prompt, pk=prompt_pk, category=category)

    prompt.text = request.POST.get('text', '').strip()
    prompt.day_number = int(request.POST.get('day_number', prompt.day_number))
    prompt.is_active = request.POST.get('is_active') == 'on'
    prompt.save()

    messages.success(request, "Prompt updated.")
    return redirect('accounts:admin_prompt_prompts', pk=pk)


@staff_member_required
@require_POST
def prompt_delete(request, pk, prompt_pk):
    """Delete a prompt."""
    category = get_object_or_404(PromptCategory, pk=pk)
    prompt = get_object_or_404(Prompt, pk=prompt_pk, category=category)

    prompt.delete()

    messages.success(request, "Prompt deleted.")
    return redirect('accounts:admin_prompt_prompts', pk=pk)
