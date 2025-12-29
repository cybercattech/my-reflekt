from django.urls import path
from . import views
from . import admin_views

app_name = 'accounts'

urlpatterns = [
    # Admin
    path('admin/subscriptions/', admin_views.subscription_dashboard, name='subscription_dashboard'),

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
]
