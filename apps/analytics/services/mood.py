"""
Mood classification service.

Classifies journal entries into mood categories:
ecstatic, happy, neutral, sad, angry

Uses VADER sentiment score for mood classification.
"""
import re


# Mood categories with associated keywords
MOOD_KEYWORDS = {
    'ecstatic': {
        'keywords': {
            'amazing', 'incredible', 'fantastic', 'perfect', 'thrilled', 'ecstatic',
            'overjoyed', 'elated', 'euphoric', 'best', 'crushing', 'milestone',
            'breakthrough', 'wonderful', 'magnificent', 'extraordinary', 'blessed',
            'grateful', 'celebrate', 'victory', 'triumph', 'dream'
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


def classify_mood(text: str, sentiment_score: float) -> tuple:
    """
    Classify text into a mood category.

    Uses VADER sentiment score combined with keyword detection.

    Args:
        text: Journal entry text
        sentiment_score: VADER sentiment score (-1.0 to 1.0)

    Returns:
        tuple: (mood: str, confidence: float, all_scores: dict)
    """
    if not text or not text.strip():
        return 'neutral', 0.5, {'neutral': 0.5}

    sentiment = sentiment_score

    # Get keyword counts
    keyword_counts = count_mood_keywords(text)

    # Calculate combined score for each mood
    scores = {mood: 0.0 for mood in MOOD_KEYWORDS.keys()}

    # Base scoring from sentiment polarity - adjusted thresholds
    if sentiment >= 0.5:
        # Very positive -> ecstatic
        scores['ecstatic'] = 2.0
        scores['happy'] = 0.5
    elif sentiment >= 0.2:
        # Positive -> happy, with some ecstatic possibility
        scores['happy'] = 1.5
        scores['ecstatic'] = sentiment
    elif sentiment >= -0.2:
        # Neutral range
        scores['neutral'] = 1.0
        if sentiment > 0:
            scores['happy'] = sentiment * 2
        elif sentiment < 0:
            scores['sad'] = abs(sentiment) * 2
    elif sentiment >= -0.5:
        # Negative -> sad
        scores['sad'] = 1.5
        scores['angry'] = abs(sentiment) * 0.5
    else:
        # Very negative -> angry
        scores['angry'] = 2.0
        scores['sad'] = 1.0

    # Add keyword influence (reduced weight so sentiment dominates)
    for mood, count in keyword_counts.items():
        if count > 0:
            scores[mood] = scores.get(mood, 0) + (count * 0.1)

    # Normalize scores
    total = sum(scores.values())
    if total > 0:
        scores = {k: v / total for k, v in scores.items()}

    # Return the highest scoring mood
    best_mood = max(scores, key=scores.get)
    confidence = scores[best_mood]

    return best_mood, confidence, scores


# Mood emoji mapping
MOOD_EMOJIS = {
    'ecstatic': '🤩',
    'happy': '😊',
    'neutral': '😐',
    'sad': '😢',
    'angry': '😠',
}


def get_mood_emoji(mood: str) -> str:
    """Get emoji for a mood category."""
    return MOOD_EMOJIS.get(mood, '😐')
