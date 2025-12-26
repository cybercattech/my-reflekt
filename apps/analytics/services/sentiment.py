"""
Sentiment analysis service using VADER.

VADER (Valence Aware Dictionary and sEntiment Reasoner) is specifically
tuned for social media and informal text, making it better for journal entries.
"""
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Initialize analyzer once (it's thread-safe)
_analyzer = None


def _get_analyzer():
    """Get or create the VADER analyzer singleton."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def get_sentiment_score(text: str) -> float:
    """
    Get sentiment polarity score for text using VADER.

    Returns:
        float: Compound score from -1.0 (very negative) to 1.0 (very positive)
    """
    if not text or not text.strip():
        return 0.0

    analyzer = _get_analyzer()
    scores = analyzer.polarity_scores(text)
    # VADER's compound score is normalized between -1 and 1
    return scores['compound']


def get_sentiment_label(score: float) -> str:
    """
    Convert sentiment score to human-readable label.

    VADER recommends these thresholds:
    - positive: compound >= 0.05
    - negative: compound <= -0.05
    - neutral: -0.05 < compound < 0.05

    Args:
        score: Sentiment compound score (-1.0 to 1.0)

    Returns:
        str: 'positive', 'negative', or 'neutral'
    """
    if score >= 0.05:
        return 'positive'
    elif score <= -0.05:
        return 'negative'
    else:
        return 'neutral'


def analyze_sentiment(text: str) -> dict:
    """
    Full sentiment analysis for a text using VADER.

    Returns:
        dict: {
            'score': float (compound score),
            'label': str,
            'positive': float (positive proportion),
            'negative': float (negative proportion),
            'neutral': float (neutral proportion)
        }
    """
    if not text or not text.strip():
        return {
            'score': 0.0,
            'label': 'neutral',
            'positive': 0.0,
            'negative': 0.0,
            'neutral': 1.0,
        }

    analyzer = _get_analyzer()
    scores = analyzer.polarity_scores(text)

    return {
        'score': scores['compound'],
        'label': get_sentiment_label(scores['compound']),
        'positive': scores['pos'],
        'negative': scores['neg'],
        'neutral': scores['neu'],
    }
