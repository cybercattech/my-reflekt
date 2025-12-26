"""
Daily Christian devotion service.

Provides daily Bible verses and reflections based on the day of the year.
No external API needed - uses a curated set of verses and reflections.
"""
from datetime import date
from typing import Dict, Optional


# Curated daily devotions (366 for leap years)
# Each entry: (verse_reference, verse_text, reflection)
DEVOTIONS = [
    # Day 1 - January 1
    {
        'reference': 'Psalm 118:24',
        'verse': 'This is the day that the Lord has made; let us rejoice and be glad in it.',
        'reflection': 'Each new day is a gift from God. No matter what yesterday brought, today offers fresh opportunities to experience His love, extend grace to others, and grow in faith. Start this day with gratitude.',
        'theme': 'New Beginnings',
    },
    # Day 2 - January 2
    {
        'reference': 'Proverbs 3:5-6',
        'verse': 'Trust in the Lord with all your heart, and do not lean on your own understanding. In all your ways acknowledge him, and he will make straight your paths.',
        'reflection': 'When life feels uncertain, remember that God sees the bigger picture. Surrendering control and trusting His guidance leads to peace, even when the path ahead is unclear.',
        'theme': 'Trust',
    },
    # Day 3 - January 3
    {
        'reference': 'Philippians 4:13',
        'verse': 'I can do all things through him who strengthens me.',
        'reflection': "Your strength doesn't come from yourself alone. When you feel inadequate or overwhelmed, remember that Christ empowers you to face every challenge. His strength is made perfect in your weakness.",
        'theme': 'Strength',
    },
    # Day 4 - January 4
    {
        'reference': 'Matthew 11:28',
        'verse': 'Come to me, all who labor and are heavy laden, and I will give you rest.',
        'reflection': 'Burnout and weariness are real. Jesus invites you to bring your burdens to Him. Rest is not a luxury—it is a sacred gift. Take time today to find rest in His presence.',
        'theme': 'Rest',
    },
    # Day 5 - January 5
    {
        'reference': 'Jeremiah 29:11',
        'verse': 'For I know the plans I have for you, declares the Lord, plans for welfare and not for evil, to give you a future and a hope.',
        'reflection': "Even when life doesn't make sense, God has a plan. His intentions toward you are good. Trust that He is working all things together for your benefit and His glory.",
        'theme': 'Hope',
    },
    # Day 6 - January 6
    {
        'reference': 'Romans 8:28',
        'verse': 'And we know that for those who love God all things work together for good, for those who are called according to his purpose.',
        'reflection': 'Not everything that happens is good, but God can redeem all things. Even in difficulty, He is at work bringing about transformation and growth. Trust the process.',
        'theme': 'Redemption',
    },
    # Day 7 - January 7
    {
        'reference': '1 Corinthians 13:4-5',
        'verse': 'Love is patient and kind; love does not envy or boast; it is not arrogant or rude. It does not insist on its own way; it is not irritable or resentful.',
        'reflection': 'Love is more than a feeling—it is a choice. Today, choose patience with the difficult person, kindness to the stranger, and humility in your interactions. Let love guide your actions.',
        'theme': 'Love',
    },
    # Day 8 - January 8
    {
        'reference': 'Psalm 46:10',
        'verse': 'Be still, and know that I am God.',
        'reflection': 'In a noisy, distracted world, stillness is revolutionary. Take a moment today to quiet your mind, set aside your to-do list, and simply rest in the presence of God.',
        'theme': 'Stillness',
    },
    # Day 9 - January 9
    {
        'reference': 'James 1:2-3',
        'verse': 'Count it all joy, my brothers, when you meet trials of various kinds, for you know that the testing of your faith produces steadfastness.',
        'reflection': 'Trials are not punishments—they are opportunities for growth. When you face difficulties, remember that perseverance builds character and deepens your faith.',
        'theme': 'Perseverance',
    },
    # Day 10 - January 10
    {
        'reference': 'Psalm 23:1',
        'verse': 'The Lord is my shepherd; I shall not want.',
        'reflection': "God provides for His children. When you feel anxious about the future or lacking in the present, remember the Good Shepherd who leads, protects, and provides for all your needs.",
        'theme': 'Provision',
    },
]


def get_daily_devotion(for_date: Optional[date] = None) -> Dict:
    """
    Get the daily devotion for a given date.

    Args:
        for_date: Date to get devotion for. Defaults to today.

    Returns:
        dict: {
            'reference': Bible verse reference,
            'verse': The verse text,
            'reflection': Daily reflection,
            'theme': Theme of the day,
            'day_number': Day of year (1-366)
        }
    """
    if for_date is None:
        for_date = date.today()

    # Get day of year (1-366)
    day_of_year = for_date.timetuple().tm_yday

    # Cycle through devotions (we have 10, so cycle them)
    # In production, you'd have 365+ devotions
    devotion_index = (day_of_year - 1) % len(DEVOTIONS)
    devotion = DEVOTIONS[devotion_index]

    return {
        'reference': devotion['reference'],
        'verse': devotion['verse'],
        'reflection': devotion['reflection'],
        'theme': devotion['theme'],
        'day_number': day_of_year,
    }


def get_devotion_for_entry(entry_date: date) -> Optional[Dict]:
    """
    Get devotion for a specific journal entry date.

    Args:
        entry_date: Date of the journal entry

    Returns:
        dict or None: Devotion data if enabled, None otherwise
    """
    return get_daily_devotion(entry_date)


def expand_devotions_database():
    """
    Placeholder for expanding the devotions database.

    In production, you could:
    - Store devotions in the database
    - Use a Bible API for verse lookup
    - Allow users to submit their own reflections
    - Import devotional content from public domain sources
    """
    pass
