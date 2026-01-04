"""
Daily journal prompts based on time context.
Generates prompts relevant to the time of day, day of week,
time of month, and season.
"""
import random
from datetime import datetime, date


def get_daily_prompt(current_date=None, current_time=None):
    """
    Generate a contextual journal prompt based on the current date and time.

    Returns a dict with:
        - prompt: The journal prompt text
        - category: The category/context of the prompt
        - icon: Bootstrap icon class
    """
    if current_date is None:
        current_date = date.today()
    if current_time is None:
        current_time = datetime.now()

    day = current_date.day
    month = current_date.month
    weekday = current_date.weekday()  # 0=Monday, 6=Sunday
    hour = current_time.hour

    # Determine time of day
    if 5 <= hour < 12:
        time_of_day = 'morning'
    elif 12 <= hour < 17:
        time_of_day = 'afternoon'
    elif 17 <= hour < 21:
        time_of_day = 'evening'
    else:
        time_of_day = 'night'

    # Determine position in month
    if day <= 5:
        month_position = 'start'
    elif day >= 25:
        month_position = 'end'
    else:
        month_position = 'middle'

    # Determine season (Northern Hemisphere)
    if month in [12, 1, 2]:
        season = 'winter'
    elif month in [3, 4, 5]:
        season = 'spring'
    elif month in [6, 7, 8]:
        season = 'summer'
    else:
        season = 'fall'

    # Special dates
    special_prompts = get_special_date_prompt(current_date)
    if special_prompts:
        return special_prompts

    # Build weighted prompt pool based on context
    prompts = []

    # Start of month prompts
    if month_position == 'start':
        prompts.extend([
            {
                'prompt': "What is one goal you want to accomplish this month?",
                'category': 'New Month',
                'icon': 'bi-calendar-plus'
            },
            {
                'prompt': "What habit would you like to build or strengthen this month?",
                'category': 'New Month',
                'icon': 'bi-arrow-repeat'
            },
            {
                'prompt': "What are you most looking forward to this month?",
                'category': 'New Month',
                'icon': 'bi-stars'
            },
            {
                'prompt': "How do you want to feel at the end of this month?",
                'category': 'New Month',
                'icon': 'bi-emoji-smile'
            },
        ])

    # End of month prompts
    elif month_position == 'end':
        prompts.extend([
            {
                'prompt': "What is one thing you learned this month?",
                'category': 'Month Reflection',
                'icon': 'bi-lightbulb'
            },
            {
                'prompt': "What accomplishment from this month are you most proud of?",
                'category': 'Month Reflection',
                'icon': 'bi-trophy'
            },
            {
                'prompt': "What would you do differently if you could restart this month?",
                'category': 'Month Reflection',
                'icon': 'bi-arrow-counterclockwise'
            },
            {
                'prompt': "Who made a positive impact on your life this month?",
                'category': 'Month Reflection',
                'icon': 'bi-people'
            },
            {
                'prompt': "What challenge did you overcome this month?",
                'category': 'Month Reflection',
                'icon': 'bi-mountain'
            },
        ])

    # Monday prompts - week intentions
    if weekday == 0:
        prompts.extend([
            {
                'prompt': "What intention do you want to set for the week ahead?",
                'category': 'Monday Motivation',
                'icon': 'bi-rocket-takeoff'
            },
            {
                'prompt': "What is your main focus for this week?",
                'category': 'Monday Motivation',
                'icon': 'bi-bullseye'
            },
            {
                'prompt': "What would make this week feel successful?",
                'category': 'Monday Motivation',
                'icon': 'bi-check2-circle'
            },
        ])

    # Friday prompts - week reflection
    elif weekday == 4:
        prompts.extend([
            {
                'prompt': "What was your biggest win this week?",
                'category': 'Friday Reflection',
                'icon': 'bi-award'
            },
            {
                'prompt': "What are you grateful for from this week?",
                'category': 'Friday Reflection',
                'icon': 'bi-heart'
            },
            {
                'prompt': "What lesson will you carry into next week?",
                'category': 'Friday Reflection',
                'icon': 'bi-bookmark-star'
            },
        ])

    # Weekend prompts
    elif weekday in [5, 6]:
        prompts.extend([
            {
                'prompt': "How are you recharging this weekend?",
                'category': 'Weekend',
                'icon': 'bi-battery-charging'
            },
            {
                'prompt': "What brings you joy outside of work?",
                'category': 'Weekend',
                'icon': 'bi-sun'
            },
            {
                'prompt': "Who would you like to spend more time with?",
                'category': 'Weekend',
                'icon': 'bi-people-fill'
            },
        ])

    # Time of day prompts
    if time_of_day == 'morning':
        prompts.extend([
            {
                'prompt': "What are you looking forward to today?",
                'category': 'Morning',
                'icon': 'bi-sunrise'
            },
            {
                'prompt': "What would make today great?",
                'category': 'Morning',
                'icon': 'bi-brightness-high'
            },
            {
                'prompt': "How are you feeling as you start this day?",
                'category': 'Morning',
                'icon': 'bi-cup-hot'
            },
        ])
    elif time_of_day == 'evening':
        prompts.extend([
            {
                'prompt': "What was the best part of your day?",
                'category': 'Evening',
                'icon': 'bi-sunset'
            },
            {
                'prompt': "What are you grateful for today?",
                'category': 'Evening',
                'icon': 'bi-heart-fill'
            },
            {
                'prompt': "What did you learn about yourself today?",
                'category': 'Evening',
                'icon': 'bi-journal-text'
            },
        ])
    elif time_of_day == 'night':
        prompts.extend([
            {
                'prompt': "What thoughts are on your mind as the day ends?",
                'category': 'Night',
                'icon': 'bi-moon-stars'
            },
            {
                'prompt': "What do you need to let go of before sleep?",
                'category': 'Night',
                'icon': 'bi-cloud-moon'
            },
        ])

    # Season-specific prompts
    if season == 'spring':
        prompts.extend([
            {
                'prompt': "What new beginnings are you nurturing in your life?",
                'category': 'Spring',
                'icon': 'bi-flower1'
            },
            {
                'prompt': "What do you want to grow or develop this season?",
                'category': 'Spring',
                'icon': 'bi-tree'
            },
        ])
    elif season == 'summer':
        prompts.extend([
            {
                'prompt': "What adventures are you craving?",
                'category': 'Summer',
                'icon': 'bi-sun-fill'
            },
            {
                'prompt': "How are you making time for rest and play?",
                'category': 'Summer',
                'icon': 'bi-umbrella-beach'
            },
        ])
    elif season == 'fall':
        prompts.extend([
            {
                'prompt': "What are you ready to release or let go of?",
                'category': 'Autumn',
                'icon': 'bi-leaf'
            },
            {
                'prompt': "What are you harvesting from seeds you planted earlier?",
                'category': 'Autumn',
                'icon': 'bi-basket'
            },
        ])
    elif season == 'winter':
        prompts.extend([
            {
                'prompt': "What does rest and restoration look like for you right now?",
                'category': 'Winter',
                'icon': 'bi-snow'
            },
            {
                'prompt': "What inner work are you focusing on during this quieter season?",
                'category': 'Winter',
                'icon': 'bi-house-heart'
            },
        ])

    # General prompts as fallback
    prompts.extend([
        {
            'prompt': "What is weighing on your mind right now?",
            'category': 'Reflection',
            'icon': 'bi-chat-heart'
        },
        {
            'prompt': "Describe a moment today that made you pause.",
            'category': 'Mindfulness',
            'icon': 'bi-pause-circle'
        },
        {
            'prompt': "What are you most curious about right now?",
            'category': 'Exploration',
            'icon': 'bi-search-heart'
        },
        {
            'prompt': "If you could tell your past self one thing, what would it be?",
            'category': 'Wisdom',
            'icon': 'bi-hourglass-split'
        },
        {
            'prompt': "What does self-care mean to you today?",
            'category': 'Self-Care',
            'icon': 'bi-heart-pulse'
        },
    ])

    # Use date as seed for consistent daily prompt
    random.seed(current_date.toordinal())
    selected = random.choice(prompts)
    random.seed()  # Reset seed

    return selected


def get_special_date_prompt(current_date):
    """Return prompts for special dates/holidays."""
    month = current_date.month
    day = current_date.day

    special_dates = {
        # New Year
        (1, 1): {
            'prompt': "What word or theme do you want to define this new year?",
            'category': 'New Year',
            'icon': 'bi-stars'
        },
        (1, 2): {
            'prompt': "What are your hopes and dreams for this year?",
            'category': 'New Year',
            'icon': 'bi-rocket-takeoff'
        },
        # Valentine's Day
        (2, 14): {
            'prompt': "What does love mean to you? How do you show love to yourself?",
            'category': "Valentine's Day",
            'icon': 'bi-heart-fill'
        },
        # First day of Spring
        (3, 20): {
            'prompt': "Spring is here! What new chapter are you ready to begin?",
            'category': 'Spring Equinox',
            'icon': 'bi-flower2'
        },
        # Earth Day
        (4, 22): {
            'prompt': "How do you connect with nature? What does the earth mean to you?",
            'category': 'Earth Day',
            'icon': 'bi-globe-americas'
        },
        # First day of Summer
        (6, 21): {
            'prompt': "Summer solstice! What light do you want to bring into your life?",
            'category': 'Summer Solstice',
            'icon': 'bi-brightness-high-fill'
        },
        # First day of Fall
        (9, 22): {
            'prompt': "Autumn begins. What are you ready to harvest from your efforts?",
            'category': 'Autumn Equinox',
            'icon': 'bi-tree-fill'
        },
        # Halloween
        (10, 31): {
            'prompt': "What fears are you ready to face and overcome?",
            'category': 'Halloween',
            'icon': 'bi-moon-fill'
        },
        # Thanksgiving (approximate - 4th Thursday)
        (11, 25): {
            'prompt': "List 10 things you're deeply grateful for this year.",
            'category': 'Thanksgiving',
            'icon': 'bi-gift'
        },
        # First day of Winter
        (12, 21): {
            'prompt': "Winter solstice - the longest night. What light lives within you?",
            'category': 'Winter Solstice',
            'icon': 'bi-snow2'
        },
        # Christmas
        (12, 25): {
            'prompt': "What moments of joy and connection are you experiencing today?",
            'category': 'Christmas',
            'icon': 'bi-gift-fill'
        },
        # New Year's Eve
        (12, 31): {
            'prompt': "As the year ends, what are you most proud of accomplishing?",
            'category': "New Year's Eve",
            'icon': 'bi-hourglass-bottom'
        },
    }

    return special_dates.get((month, day))


def get_prompt_for_user(user, current_date=None, current_time=None):
    """
    Get a personalized prompt based on user's selected categories.

    1. If user has selected prompt categories, get prompts from those categories
    2. If no categories selected, fall back to the default category
    3. Ultimate fallback: legacy context-aware prompts
    """
    from django.utils import timezone
    from .models import UserPromptPreference, PromptCategory, Prompt

    if current_date is None:
        current_date = timezone.now().date()

    # Check if user has selected any prompt categories
    preferences = UserPromptPreference.objects.filter(user=user).select_related('category')

    if preferences.exists():
        # Get all prompts from user's selected categories
        category_ids = preferences.values_list('category_id', flat=True)
        prompts = Prompt.objects.filter(
            category_id__in=category_ids,
            is_active=True
        ).select_related('category')

        if prompts.exists():
            # Daily rotation using date as seed for consistency
            prompt_list = list(prompts)
            random.seed(current_date.toordinal())
            selected = random.choice(prompt_list)
            random.seed()

            return {
                'prompt': selected.text,
                'category': selected.category.name,
                'icon': selected.category.icon
            }

    # Fall back to default category if no preferences
    default_category = PromptCategory.objects.filter(
        is_default=True,
        is_active=True
    ).first()

    if default_category:
        prompts = default_category.prompts.filter(is_active=True)
        if prompts.exists():
            prompt_list = list(prompts)
            random.seed(current_date.toordinal())
            selected = random.choice(prompt_list)
            random.seed()

            return {
                'prompt': selected.text,
                'category': default_category.name,
                'icon': default_category.icon
            }

    # Ultimate fallback: legacy context-aware prompts
    return get_daily_prompt(current_date, current_time)
