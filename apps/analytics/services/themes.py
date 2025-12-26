"""
Theme and keyword extraction service.

Identifies themes in journal entries like:
work, family, health, relationships, travel, etc.
"""
import re
from collections import Counter


# Theme definitions with associated keywords
THEME_DEFINITIONS = {
    'work': {
        'keywords': {
            'work', 'job', 'office', 'boss', 'meeting', 'project', 'deadline',
            'colleague', 'career', 'promotion', 'salary', 'client', 'business',
            'professional', 'team', 'manager', 'employee', 'company', 'corporate'
        }
    },
    'family': {
        'keywords': {
            'family', 'mom', 'dad', 'mother', 'father', 'parent', 'child',
            'children', 'son', 'daughter', 'brother', 'sister', 'wife', 'husband',
            'spouse', 'kids', 'baby', 'grandma', 'grandpa', 'aunt', 'uncle'
        }
    },
    'health': {
        'keywords': {
            'health', 'doctor', 'hospital', 'sick', 'medicine', 'workout',
            'exercise', 'gym', 'run', 'running', 'weight', 'diet', 'sleep',
            'tired', 'energy', 'pain', 'therapy', 'mental', 'anxiety', 'stress'
        }
    },
    'relationships': {
        'keywords': {
            'friend', 'friends', 'friendship', 'dating', 'relationship', 'love',
            'partner', 'boyfriend', 'girlfriend', 'breakup', 'marriage', 'wedding',
            'romantic', 'date', 'social', 'connection'
        }
    },
    'personal_growth': {
        'keywords': {
            'learn', 'learning', 'growth', 'improve', 'goal', 'goals', 'habit',
            'reading', 'book', 'course', 'skill', 'development', 'progress',
            'achievement', 'success', 'failure', 'lesson', 'reflection'
        }
    },
    'creativity': {
        'keywords': {
            'write', 'writing', 'create', 'creative', 'art', 'music', 'paint',
            'design', 'blog', 'story', 'poem', 'photography', 'craft', 'hobby',
            'project', 'build', 'make'
        }
    },
    'travel': {
        'keywords': {
            'travel', 'trip', 'vacation', 'flight', 'airport', 'hotel', 'visit',
            'explore', 'adventure', 'journey', 'road', 'drive', 'destination'
        }
    },
    'finance': {
        'keywords': {
            'money', 'finance', 'budget', 'save', 'saving', 'invest', 'investment',
            'debt', 'loan', 'bill', 'expense', 'income', 'financial', 'bank'
        }
    },
    'spirituality': {
        'keywords': {
            'god', 'faith', 'pray', 'prayer', 'church', 'spiritual', 'soul',
            'meditation', 'mindfulness', 'believe', 'blessing', 'grateful',
            'purpose', 'meaning'
        }
    },
    'technology': {
        'keywords': {
            'code', 'coding', 'programming', 'software', 'app', 'computer',
            'tech', 'technology', 'data', 'website', 'developer', 'python',
            'database', 'algorithm'
        }
    }
}

# Common stop words to exclude from keywords
STOP_WORDS = {
    # Time words
    'today', 'tomorrow', 'yesterday', 'day', 'days', 'week', 'weeks', 'month',
    'months', 'year', 'years', 'time', 'times', 'morning', 'afternoon', 'evening',
    'night', 'hour', 'hours', 'minute', 'minutes', 'second', 'seconds',
    # Common words
    'thing', 'things', 'way', 'ways', 'place', 'places', 'people', 'person',
    'lot', 'lots', 'bit', 'kind', 'sort', 'type', 'part', 'parts',
    # Pronouns and articles (in case any slip through)
    'something', 'anything', 'everything', 'nothing', 'someone', 'anyone',
    'everyone', 'other', 'others', 'another', 'same', 'different',
    # Very common verbs
    'going', 'getting', 'making', 'doing', 'being', 'having', 'saying',
    'thinking', 'coming', 'looking', 'wanting', 'using', 'finding', 'giving',
    'telling', 'trying', 'leaving', 'feeling', 'becoming', 'putting',
    # Generic nouns
    'stuff', 'matter', 'case', 'point', 'fact', 'idea', 'reason', 'example',
    'number', 'group', 'world', 'life', 'hand', 'home', 'room', 'house',
    # Contractions that might appear
    'don', 'didn', 'doesn', 'won', 'wouldn', 'couldn', 'shouldn', 'isn',
    'aren', 'wasn', 'weren', 'hasn', 'haven', 'hadn', 'll', 've', 're',
}


def extract_themes(text: str, min_count: int = 2) -> list:
    """
    Extract themes from text based on keyword matching.

    Args:
        text: Journal entry text
        min_count: Minimum keyword matches to include theme

    Returns:
        list: List of detected themes, sorted by relevance
    """
    if not text or not text.strip():
        return []

    text_lower = text.lower()
    words = set(re.findall(r'\b\w+\b', text_lower))

    theme_scores = {}
    for theme, data in THEME_DEFINITIONS.items():
        matches = words.intersection(data['keywords'])
        count = len(matches)
        if count >= min_count:
            theme_scores[theme] = count

    # Sort by count descending
    sorted_themes = sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)
    return [theme for theme, _ in sorted_themes]


def extract_keywords(text: str, top_n: int = 10) -> list:
    """
    Extract top keywords from text.

    Only includes real, meaningful words:
    - Must be alphabetic (no numbers, punctuation, or mixed)
    - Must be at least 3 characters
    - Must not be a stop word
    - Must appear more than once OR be a significant word

    Args:
        text: Journal entry text
        top_n: Number of keywords to return

    Returns:
        list: Top keywords
    """
    if not text or not text.strip():
        return []

    # Clean text: remove markdown, URLs, special characters
    clean_text = text.lower()

    # Remove URLs
    clean_text = re.sub(r'https?://\S+', '', clean_text)

    # Remove markdown formatting
    clean_text = re.sub(r'[*_#>`~\[\](){}]', ' ', clean_text)

    # Remove time patterns like 12:00:00
    clean_text = re.sub(r'\d{1,2}:\d{2}(:\d{2})?\s*(am|pm)?', '', clean_text)

    # Remove dates like 12/25/2024 or 2024-12-25
    clean_text = re.sub(r'\d{1,4}[-/]\d{1,2}[-/]\d{1,4}', '', clean_text)

    # Extract only alphabetic words (no numbers, no punctuation attached)
    words = re.findall(r'\b[a-z]{3,}\b', clean_text)

    # Filter out stop words and very short words
    filtered_words = [
        word for word in words
        if word not in STOP_WORDS
        and len(word) >= 3
        and not word.endswith("'s")  # Possessives
        and word not in {'the', 'and', 'but', 'for', 'are', 'was', 'were', 'been',
                         'have', 'has', 'had', 'will', 'would', 'could', 'should',
                         'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
                         'that', 'this', 'these', 'those', 'which', 'what', 'who',
                         'whom', 'whose', 'where', 'when', 'why', 'how', 'all',
                         'each', 'every', 'both', 'few', 'more', 'most', 'some',
                         'any', 'such', 'not', 'only', 'own', 'very', 'just',
                         'also', 'now', 'then', 'than', 'too', 'here', 'there',
                         'out', 'about', 'into', 'over', 'after', 'before',
                         'between', 'under', 'again', 'further', 'once', 'with',
                         'from', 'they', 'them', 'their', 'she', 'her', 'him',
                         'his', 'its', 'our', 'your', 'you', 'myself', 'yourself',
                         'himself', 'herself', 'itself', 'ourselves', 'themselves',
                         'really', 'actually', 'basically', 'definitely', 'probably',
                         'certainly', 'maybe', 'perhaps', 'though', 'although',
                         'however', 'still', 'yet', 'already', 'even', 'ever',
                         'never', 'always', 'often', 'sometimes', 'usually',
                         'especially', 'particularly', 'generally', 'specifically'}
    ]

    # Count occurrences
    counter = Counter(filtered_words)

    # Get most common
    return [word for word, count in counter.most_common(top_n)]


def get_theme_display_name(theme: str) -> str:
    """Convert theme key to display name."""
    display_names = {
        'work': 'Work & Career',
        'family': 'Family',
        'health': 'Health & Wellness',
        'relationships': 'Relationships',
        'personal_growth': 'Personal Growth',
        'creativity': 'Creativity & Writing',
        'travel': 'Travel',
        'finance': 'Finance',
        'spirituality': 'Spirituality & Faith',
        'technology': 'Technology',
    }
    return display_names.get(theme, theme.replace('_', ' ').title())
