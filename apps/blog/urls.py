from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # Public URLs
    path('', views.post_list, name='post_list'),
    path('category/<slug:slug>/', views.category_posts, name='category'),
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),

    # Admin URLs
    path('manage/', views.admin_post_list, name='admin_list'),
    path('manage/new/', views.admin_post_create, name='admin_create'),
    path('manage/<int:pk>/edit/', views.admin_post_edit, name='admin_edit'),
    path('manage/<int:pk>/delete/', views.admin_post_delete, name='admin_delete'),
    path('manage/<int:pk>/toggle/', views.admin_post_toggle_status, name='admin_toggle'),
    path('manage/autosave/', views.admin_post_autosave, name='admin_autosave'),
    path('manage/categories/', views.admin_category_list, name='admin_categories'),
    path('manage/categories/<int:pk>/delete/', views.admin_category_delete, name='admin_category_delete'),
]
