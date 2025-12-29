"""
Mood classification service using VADER.

Classifies journal entries into mood categories:
ecstatic, happy, neutral, sad, angry

Uses VADER sentiment for consistency with sentiment analysis.
"""
import re
from .sentiment import get_sentiment_score


# Standard mood emoji mapping - single source of truth
MOOD_EMOJIS = {
    'ecstatic': '🤩',
    'happy': '😊',
    'neutral': '😐',
    'sad': '😢',
    'angry': '😠',
}

# Standard mood colors (hex) - single source of truth
MOOD_COLORS = {
    'ecstatic': '#8b5cf6',  # purple
    'happy': '#22c55e',     # green
    'neutral': '#6b7280',   # gray
    'sad': '#3b82f6',       # blue
    'angry': '#ef4444',     # red
}


# Mood categories with associated keywords (for boosting/adjusting)
MOOD_KEYWORDS = {
    'ecstatic': {
        'keywords': {
            'amazing', 'incredible', 'fantastic', 'perfect', 'thrilled', 'ecstatic',
            'overjoyed', 'elated', 'euphoric', 'best', 'crushing', 'milestone',
            'breakthrough', 'wonderful', 'magnificent', 'extraordinary', 'blessed',
            'grateful', 'celebrate', 'victory', 'triumph'
        },
        'weight': 0.3
    },
    'happy': {
        'keywords': {
            'happy', 'good', 'great', 'nice', 'enjoy', 'pleased', 'satisfied',
            'content', 'cheerful', 'glad', 'delighted', 'pleasant', 'fun',
            'productive', 'accomplished', 'peaceful', 'relaxed', 'calm', 'love',
            'excited', 'proud', 'thankful'
        },
        'weight': 0.15
    },
    'neutral': {
        'keywords': {
            'okay', 'fine', 'normal', 'regular', 'usual', 'routine',
            'uneventful', 'ordinary', 'typical', 'average'
        },
        'weight': 0.0
    },
    'sad': {
        'keywords': {
            'sad', 'unhappy', 'down', 'disappointed', 'upset', 'hurt', 'pain',
            'miss', 'lonely', 'melancholy', 'depressed', 'heartbroken', 'crying',
            'tears', 'sorrow', 'grief', 'loss', 'regret', 'hopeless', 'empty',
            'worried', 'anxious'
        },
        'weight': -0.15
    },
    'angry': {
        'keywords': {
            'angry', 'furious', 'mad', 'frustrated', 'irritated', 'annoyed', 'pissed',
            'rage', 'hate', 'resent', 'bitter', 'outraged', 'livid', 'infuriated',
            'aggravated', 'exasperated', 'disgusted', 'despise'
        },
        'weight': -0.3
    }
}


def count_mood_keywords(text: str) -> dict:
    """
    Count keywords for each mood category in text.

    Returns:
        dict: {mood: count} for each mood
    """
    text_lower = text.lower()
    words = set(re.findall(r'\b\w+\b', text_lower))

    counts = {}
    for mood, data in MOOD_KEYWORDS.items():
        count = len(words.intersection(data['keywords']))
        # Also check for multi-word phrases
        for phrase in data['keywords']:
            if ' ' in phrase and phrase in text_lower:
                count += 2  # Weight phrases higher
        counts[mood] = count

    return counts


def classify_mood(text: str) -> tuple:
    """
    Classify text into a mood category using VADER sentiment.

    Uses VADER for base sentiment, with keyword detection for fine-tuning.
    This ensures mood classification aligns with sentiment score.

    Args:
        text: Journal entry text

    Returns:
        tuple: (mood: str, confidence: float, all_scores: dict)
    """
    if not text or not text.strip():
        return 'neutral', 0.5, {'neutral': 0.5}

    # Get VADER sentiment score (same as used for sentiment_score)
    sentiment = get_sentiment_score(text)

    # Get keyword counts for fine-tuning
    keyword_counts = count_mood_keywords(text)

    # Calculate combined score for each mood
    scores = {mood: 0.0 for mood in MOOD_KEYWORDS.keys()}

    # Base scoring from VADER sentiment
    # VADER compound score ranges from -1 to 1
    if sentiment >= 0.5:
        # Very positive -> ecstatic
        scores['ecstatic'] = sentiment * 1.5
        scores['happy'] = sentiment * 0.5
    elif sentiment >= 0.05:
        # Positive -> happy (with some ecstatic boost for high scores)
        scores['happy'] = sentiment * 2
        scores['ecstatic'] = max(0, (sentiment - 0.3) * 2)
    elif sentiment > -0.05:
        # Neutral range
        scores['neutral'] = 1 - abs(sentiment) * 5
    elif sentiment >= -0.5:
        # Negative -> sad
        scores['sad'] = abs(sentiment) * 2
        scores['angry'] = abs(sentiment) * 0.5
    else:
        # Very negative -> could be angry or very sad
        scores['angry'] = abs(sentiment) * 1.2
        scores['sad'] = abs(sentiment)

    # Add keyword influence (can shift between ecstatic/happy or sad/angry)
    for mood, count in keyword_counts.items():
        if count > 0:
            scores[mood] = scores.get(mood, 0) + (count * 0.2)

    # Normalize scores
    total = sum(scores.values())
    if total > 0:
        scores = {k: v / total for k, v in scores.items()}

    # Return the highest scoring mood
    best_mood = max(scores, key=scores.get)
    confidence = scores[best_mood]

    return best_mood, confidence, scores


def get_mood_emoji(mood: str) -> str:
    """Get emoji for a mood category."""
    return MOOD_EMOJIS.get(mood, '😐')


def get_mood_color(mood: str) -> str:
    """Get CSS class suffix for a mood category."""
    # Returns the mood name itself for use with badge-mood-{mood} classes
    valid_moods = {'ecstatic', 'happy', 'neutral', 'sad', 'angry'}
    return mood if mood in valid_moods else 'neutral'


def get_mood_hex_color(mood: str) -> str:
    """Get hex color for a mood category."""
    return MOOD_COLORS.get(mood, '#6b7280')
