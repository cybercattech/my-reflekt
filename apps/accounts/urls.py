from django.urls import path
from . import views
from . import admin_views
from apps.challenges import admin_views as challenge_admin_views
from apps.journal import admin_views as journal_admin_views

app_name = 'accounts'

urlpatterns = [
    # Admin Panel
    path('manage/', admin_views.admin_panel, name='admin_panel'),
    path('manage/users/', admin_views.user_list, name='admin_user_list'),
    path('manage/users/create/', admin_views.create_user, name='admin_create_user'),
    path('manage/users/<int:user_id>/', admin_views.user_detail, name='admin_user_detail'),
    path('manage/users/<int:user_id>/edit/', admin_views.edit_user, name='admin_edit_user'),
    path('manage/users/<int:user_id>/toggle-premium/', admin_views.toggle_premium, name='admin_toggle_premium'),
    path('manage/users/<int:user_id>/delete/', admin_views.delete_user, name='admin_delete_user'),
    path('manage/users/<int:user_id>/verify-email/', admin_views.verify_user_email, name='admin_verify_email'),
    path('manage/users/<int:user_id>/unverify-email/', admin_views.unverify_user_email, name='admin_unverify_email'),
    path('manage/users/<int:user_id>/reset-password/', admin_views.reset_user_password, name='admin_reset_password'),
    path('manage/subscriptions/', admin_views.subscription_dashboard, name='subscription_dashboard'),
    path('manage/emails/', admin_views.email_templates_list, name='admin_email_templates'),
    path('manage/emails/<str:template_id>/preview/', admin_views.email_template_preview, name='admin_email_preview'),
    path('manage/emails/<str:template_id>/send-test/', admin_views.send_test_email, name='admin_send_test_email'),
    path('manage/feedback/', admin_views.feedback_list, name='admin_feedback_list'),
    path('manage/feedback/<int:feedback_id>/', admin_views.feedback_detail, name='admin_feedback_detail'),
    path('manage/feedback/<int:feedback_id>/status/', admin_views.feedback_update_status, name='admin_feedback_status'),

    # Challenge Management
    path('manage/challenges/', challenge_admin_views.challenge_admin_list, name='admin_challenge_list'),
    path('manage/challenges/create/', challenge_admin_views.challenge_create, name='admin_challenge_create'),
    path('manage/challenges/<int:pk>/edit/', challenge_admin_views.challenge_edit, name='admin_challenge_edit'),
    path('manage/challenges/<int:pk>/delete/', challenge_admin_views.challenge_delete, name='admin_challenge_delete'),
    path('manage/challenges/<int:pk>/prompts/', challenge_admin_views.challenge_prompts, name='admin_challenge_prompts'),
    path('manage/challenges/<int:pk>/prompts/add/', challenge_admin_views.prompt_add, name='admin_prompt_add'),
    path('manage/challenges/<int:pk>/prompts/<int:prompt_pk>/edit/', challenge_admin_views.prompt_edit, name='admin_prompt_edit'),
    path('manage/challenges/<int:pk>/prompts/<int:prompt_pk>/delete/', challenge_admin_views.prompt_delete, name='admin_prompt_delete'),
    path('manage/challenges/<int:pk>/stats/', challenge_admin_views.challenge_stats, name='admin_challenge_stats'),

    # Prompt Category Management (Journal Prompts)
    path('manage/prompts/', journal_admin_views.prompt_category_list, name='admin_prompt_list'),
    path('manage/prompts/create/', journal_admin_views.prompt_category_create, name='admin_prompt_category_create'),
    path('manage/prompts/<int:pk>/edit/', journal_admin_views.prompt_category_edit, name='admin_prompt_category_edit'),
    path('manage/prompts/<int:pk>/delete/', journal_admin_views.prompt_category_delete, name='admin_prompt_category_delete'),
    path('manage/prompts/<int:pk>/prompts/', journal_admin_views.prompt_prompts, name='admin_prompt_prompts'),
    path('manage/prompts/<int:pk>/prompts/add/', journal_admin_views.prompt_add, name='admin_journal_prompt_add'),
    path('manage/prompts/<int:pk>/prompts/<int:prompt_pk>/edit/', journal_admin_views.prompt_edit, name='admin_journal_prompt_edit'),
    path('manage/prompts/<int:pk>/prompts/<int:prompt_pk>/delete/', journal_admin_views.prompt_delete, name='admin_journal_prompt_delete'),

    # Subscription
    path('pricing/', views.pricing_view, name='pricing'),
    path('select-plan/', views.select_plan, name='select_plan'),
    path('process-plan/', views.process_plan_selection, name='process_plan_selection'),
    path('upgrade/', views.upgrade_view, name='upgrade'),
    path('subscription/manage/', views.manage_subscription, name='manage_subscription'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('checkout/create/', views.create_checkout, name='create_checkout'),
    path('checkout/success/', views.checkout_success, name='checkout_success'),
    path('checkout/cancel/', views.checkout_cancel, name='checkout_cancel'),
    path('stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),

    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.profile_update, name='profile_update'),

    # Friends
    path('friends/send-request/', views.send_friend_request_view, name='send_friend_request'),
    path('friends/accept/<int:request_id>/', views.accept_friend_request_view, name='accept_friend_request'),
    path('friends/deny/<int:request_id>/', views.deny_friend_request_view, name='deny_friend_request'),
    path('friends/cancel/<int:request_id>/', views.cancel_friend_request_view, name='cancel_friend_request'),
    path('friends/unfriend/<int:friend_id>/', views.unfriend_view, name='unfriend'),

    # Invitations
    path('invitations/accept/<int:invitation_id>/', views.accept_invitation_view, name='accept_invitation'),
    path('invitations/deny/<int:invitation_id>/', views.deny_invitation_view, name='deny_invitation'),
    path('invitations/cancel/<int:invitation_id>/', views.cancel_invitation_view, name='cancel_invitation'),

    # API
    path('api/search-users/', views.search_users_view, name='search_users'),
    path('api/friends/', views.friends_list_api, name='friends_list_api'),

    # Family Plan Management
    path('family/', views.family_management, name='family_management'),
    path('family/add/', views.add_family_member, name='add_family_member'),
    path('family/remove/<int:member_id>/', views.remove_family_member, name='remove_family_member'),
    path('family/accept/<int:invitation_id>/', views.accept_family_invitation, name='accept_family_invitation'),
    path('family/decline/<int:invitation_id>/', views.decline_family_invitation, name='decline_family_invitation'),

    # Legal
    path('privacy/', views.privacy_policy, name='privacy'),
    path('terms/', views.terms_of_service, name='terms'),

    # Feedback
    path('feedback/submit/', views.submit_feedback, name='submit_feedback'),

    # Tutorial
    path('tutorial/complete/', views.complete_tutorial, name='complete_tutorial'),
    path('tutorial/reset/', views.reset_tutorial, name='reset_tutorial'),

    # Public pages
    path('changelog/', views.changelog, name='changelog'),
]
