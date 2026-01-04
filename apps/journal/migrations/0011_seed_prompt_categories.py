# Generated data migration to seed prompt categories and prompts

from django.db import migrations


PROMPT_CATEGORIES = [
    {
        'name': 'General',
        'slug': 'general',
        'description': 'A variety of thoughtful prompts for daily reflection and journaling.',
        'icon': 'bi-lightbulb',
        'color': '#7c3aed',
        'is_default': True,
        'display_order': 0,
        'prompts': [
            "What's on your mind today?",
            "What are you grateful for right now?",
            "Describe a moment that made you smile recently.",
            "What's something you learned this week?",
            "How are you feeling in this moment?",
            "What's one thing you'd like to accomplish today?",
            "Write about a person who has influenced your life.",
            "What does a perfect day look like to you?",
            "What's something you're looking forward to?",
            "Reflect on a challenge you overcame recently.",
            "What brings you peace?",
            "Describe your ideal environment for relaxation.",
            "What's a goal you're working toward?",
            "Write about something that inspired you recently.",
            "What would you tell your younger self?",
        ]
    },
    {
        'name': 'Teens',
        'slug': 'teens',
        'description': 'Prompts designed for teenage journalers navigating life, identity, and growth.',
        'icon': 'bi-stars',
        'color': '#ec4899',
        'is_default': False,
        'display_order': 1,
        'prompts': [
            "What's something about yourself you're proud of?",
            "Describe your ideal future in 5 years.",
            "What's a challenge you're facing at school or with friends?",
            "Who is someone you look up to and why?",
            "What makes you different from everyone else?",
            "Write about a time you stood up for yourself.",
            "What's something you wish adults understood about you?",
            "Describe your perfect weekend.",
            "What are three things that make you happy?",
            "Write about a friendship that means a lot to you.",
            "What's something new you'd like to try?",
            "How do you handle stress?",
            "What does 'being yourself' mean to you?",
            "Write about a mistake you learned from.",
            "What advice would you give to your future self?",
        ]
    },
    {
        'name': 'Anxiety',
        'slug': 'anxiety',
        'description': 'Calming prompts to help process anxious thoughts and find grounding.',
        'icon': 'bi-cloud-sun',
        'color': '#06b6d4',
        'is_default': False,
        'display_order': 2,
        'prompts': [
            "What are you worried about right now? Write it all out.",
            "List 5 things you can see, 4 you can hear, 3 you can touch, 2 you can smell, 1 you can taste.",
            "What's the worst that could happen? Now, what's most likely to happen?",
            "Write about a time you felt anxious but everything turned out okay.",
            "What are three things within your control right now?",
            "Describe a place where you feel completely safe and calm.",
            "What would you say to a friend who was feeling this way?",
            "List 10 things that are going right in your life.",
            "What helps you feel grounded when you're anxious?",
            "Write about something you're avoiding. What's the first small step?",
            "What's one kind thing you can do for yourself today?",
            "Describe your anxiety as a weather pattern. What would help it pass?",
            "What are you grateful for in this moment?",
            "Write a letter to your anxious thoughts.",
            "What's one thing you can let go of today?",
        ]
    },
    {
        'name': 'OCD',
        'slug': 'ocd',
        'description': 'Prompts to help process intrusive thoughts and practice acceptance.',
        'icon': 'bi-puzzle',
        'color': '#8b5cf6',
        'is_default': False,
        'display_order': 3,
        'prompts': [
            "What intrusive thoughts came up today? Remember, thoughts are not facts.",
            "Describe a moment when you resisted a compulsion. How did it feel?",
            "What would life look like without OCD? Describe one aspect.",
            "Write about uncertainty and how you can practice accepting it.",
            "What's one thing you did today despite feeling anxious?",
            "List three values that are important to you, separate from OCD.",
            "What would you tell someone else struggling with similar thoughts?",
            "Describe a small victory you had today over a ritual or compulsion.",
            "What are you learning about yourself through this journey?",
            "Write about a time you showed yourself compassion.",
            "How did you practice 'good enough' today instead of perfect?",
            "What activities help you feel present and engaged?",
            "Write about the difference between you and your OCD.",
            "What's one step toward living by your values today?",
            "Describe a moment of peace you experienced recently.",
        ]
    },
    {
        'name': 'Depression',
        'slug': 'depression',
        'description': 'Gentle prompts for processing difficult emotions and finding small lights.',
        'icon': 'bi-brightness-alt-high',
        'color': '#3b82f6',
        'is_default': False,
        'display_order': 4,
        'prompts': [
            "How are you really feeling today? There's no wrong answer.",
            "What's one small thing you accomplished today?",
            "Write about a time when you felt hopeful.",
            "What's one thing that brought even a tiny bit of comfort recently?",
            "Describe someone who cares about you.",
            "What would your ideal support look like right now?",
            "List three things you're proud of, no matter how small.",
            "Write a letter to yourself on a good day to read on hard days.",
            "What's one thing you can do to take care of yourself today?",
            "Describe a moment when you felt connected to something or someone.",
            "What does self-compassion look like for you?",
            "Write about something you used to enjoy. Could you try a small piece of it?",
            "What's one thing you're looking forward to, even slightly?",
            "Describe a safe, comforting space, real or imagined.",
            "What would you say to comfort a friend feeling this way?",
        ]
    },
    {
        'name': 'Gratitude',
        'slug': 'gratitude',
        'description': 'Daily prompts to cultivate appreciation and notice the good.',
        'icon': 'bi-heart',
        'color': '#f59e0b',
        'is_default': False,
        'display_order': 5,
        'prompts': [
            "List three things you're grateful for today.",
            "Who made a positive difference in your life recently?",
            "What's a simple pleasure you enjoyed today?",
            "Write about a memory that makes you smile.",
            "What's something about your body you're grateful for?",
            "Describe a skill or ability you appreciate having.",
            "What's a challenge that taught you something valuable?",
            "Who is someone you haven't thanked but should?",
            "What's a modern convenience you're grateful for?",
            "Describe a place that brings you joy.",
            "What's a book, song, or movie you're grateful exists?",
            "List five small things that made today better.",
            "What's something about this season you appreciate?",
            "Write about a relationship you treasure.",
            "What's an unexpected blessing you've received?",
        ]
    },
    {
        'name': 'Self-Compassion',
        'slug': 'self-compassion',
        'description': 'Prompts to practice kindness toward yourself and embrace imperfection.',
        'icon': 'bi-emoji-smile',
        'color': '#f472b6',
        'is_default': False,
        'display_order': 6,
        'prompts': [
            "What would you say to a friend going through what you're facing?",
            "Write about a mistake you made and offer yourself forgiveness.",
            "What do you need to hear right now?",
            "Describe three things you like about yourself.",
            "How can you be gentler with yourself today?",
            "Write about a time you were too hard on yourself.",
            "What does it mean to treat yourself with kindness?",
            "List your strengths and acknowledge them.",
            "Write a love letter to yourself.",
            "What do you need permission to feel or do?",
            "Describe how you'd comfort yourself as a child.",
            "What self-critical thought can you challenge today?",
            "How have you grown in the past year?",
            "What boundaries do you need to set for your wellbeing?",
            "Write about accepting yourself exactly as you are today.",
        ]
    },
    {
        'name': 'Stress Management',
        'slug': 'stress',
        'description': 'Prompts to help process stress and find balance in busy times.',
        'icon': 'bi-water',
        'color': '#14b8a6',
        'is_default': False,
        'display_order': 7,
        'prompts': [
            "What's causing you the most stress right now?",
            "List everything on your mind, then circle what you can control.",
            "What's one thing you can delegate or let go of?",
            "Describe your ideal stress-free evening.",
            "What helps you decompress after a hard day?",
            "Write about a time you successfully managed stress.",
            "What boundaries would help reduce your stress?",
            "List three things you can do to take a break today.",
            "What does balance look like for you?",
            "Write about what you'd do with an extra hour today.",
            "What's draining your energy right now?",
            "Describe activities that recharge you.",
            "What can you say 'no' to this week?",
            "How does your body tell you it's stressed?",
            "What's one small change that could reduce daily stress?",
        ]
    },
    {
        'name': 'Mindfulness',
        'slug': 'mindfulness',
        'description': 'Prompts to practice present-moment awareness and conscious living.',
        'icon': 'bi-flower1',
        'color': '#22c55e',
        'is_default': False,
        'display_order': 8,
        'prompts': [
            "Describe exactly what you notice around you right now.",
            "What sensations do you feel in your body at this moment?",
            "Write about eating your last meal mindfully. What did you notice?",
            "Describe the sounds you can hear right now.",
            "What emotions are present for you today? Just notice them.",
            "Write about something beautiful you observed today.",
            "How does your breath feel right now?",
            "Describe a routine activity as if experiencing it for the first time.",
            "What thoughts keep pulling you away from the present?",
            "Write about a moment of stillness you experienced.",
            "Describe the texture and weight of an object near you.",
            "What can you appreciate about this exact moment?",
            "Write about walking slowly and noticing each step.",
            "How does being present change your experience?",
            "Describe the quality of light where you are right now.",
        ]
    },
    {
        'name': 'Relationships',
        'slug': 'relationships',
        'description': 'Prompts to reflect on connections with others and nurture bonds.',
        'icon': 'bi-people',
        'color': '#ef4444',
        'is_default': False,
        'display_order': 9,
        'prompts': [
            "Write about someone who makes you feel understood.",
            "What qualities do you value most in a friend?",
            "Describe a relationship you'd like to strengthen.",
            "What's something you appreciate about your family?",
            "Write about a meaningful conversation you had recently.",
            "How do you show love to the people in your life?",
            "What would you like to communicate to someone important?",
            "Describe a time someone showed you kindness.",
            "What relationship patterns would you like to change?",
            "Write about forgiveness—given or received.",
            "How do you nurture your closest relationships?",
            "What boundaries help you have healthier relationships?",
            "Describe your ideal way to spend time with loved ones.",
            "Write a letter to someone you've lost touch with.",
            "What have your relationships taught you about yourself?",
        ]
    },
]


def seed_prompts(apps, schema_editor):
    PromptCategory = apps.get_model('journal', 'PromptCategory')
    Prompt = apps.get_model('journal', 'Prompt')

    for cat_data in PROMPT_CATEGORIES:
        category = PromptCategory.objects.create(
            name=cat_data['name'],
            slug=cat_data['slug'],
            description=cat_data['description'],
            icon=cat_data['icon'],
            color=cat_data['color'],
            is_default=cat_data['is_default'],
            display_order=cat_data['display_order'],
        )

        for i, prompt_text in enumerate(cat_data['prompts'], start=1):
            Prompt.objects.create(
                category=category,
                text=prompt_text,
                day_number=i,
                is_active=True,
            )


def reverse_seed(apps, schema_editor):
    PromptCategory = apps.get_model('journal', 'PromptCategory')
    Prompt = apps.get_model('journal', 'Prompt')

    # Delete all prompts and categories
    Prompt.objects.all().delete()
    PromptCategory.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('journal', '0010_add_prompt_preferences'),
    ]

    operations = [
        migrations.RunPython(seed_prompts, reverse_seed),
    ]
