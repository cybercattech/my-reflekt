from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('month/<int:year>/<int:month>/', views.monthly_view, name='monthly'),
    path('year/<int:year>/', views.yearly_view, name='yearly'),
    path('year/<int:year>/regenerate/', views.regenerate_yearly, name='regenerate_yearly'),

    # Capture analytics
    path('captures/', views.captures_dashboard, name='captures'),
    path('captures/books/', views.books_dashboard, name='books'),
    path('captures/media/', views.media_dashboard, name='media'),
    path('captures/people/', views.people_dashboard, name='people'),
    path('captures/fitness/', views.fitness_dashboard, name='fitness'),
    path('captures/travel/', views.travel_dashboard, name='travel'),
    path('captures/wellness/', views.wellness_dashboard, name='wellness'),

    # Person API endpoints
    path('api/person/<int:pk>/', views.person_detail, name='person_detail'),
    path('api/person/<int:pk>/update/', views.person_update, name='person_update'),
    path('api/person/<int:pk>/delete/', views.person_delete, name='person_delete'),

    # Book API endpoints
    path('api/book/<int:pk>/', views.book_detail, name='book_detail'),
    path('api/book/<int:pk>/update/', views.book_update, name='book_update'),
    path('api/book/<int:pk>/delete/', views.book_delete, name='book_delete'),

    # Media API endpoints
    path('api/media/<int:pk>/', views.media_detail, name='media_detail'),
    path('api/media/<int:pk>/update/', views.media_update, name='media_update'),
    path('api/media/<int:pk>/delete/', views.media_delete, name='media_delete'),

    # Workout API endpoints
    path('api/workout/<int:pk>/', views.workout_detail, name='workout_detail'),
    path('api/workout/<int:pk>/update/', views.workout_update, name='workout_update'),
    path('api/workout/<int:pk>/delete/', views.workout_delete, name='workout_delete'),
]
