"""
Template filters for rendering Markdown content with MyST directive support.
"""
import re
import markdown
from django import template
from django.utils.safestring import mark_safe
import bleach

register = template.Library()

# Allowed HTML tags after markdown rendering
ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr',
    'strong', 'em', 'b', 'i', 'u', 's', 'strike',
    'ul', 'ol', 'li',
    'blockquote', 'code', 'pre',
    'a', 'img',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'div', 'span',
    'sup', 'sub',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'code': ['class'],
    'pre': ['class'],
    'div': ['class'],
    'span': ['class', 'data-tag'],
    'th': ['align'],
    'td': ['align'],
}

# MyST directive styles
DIRECTIVE_STYLES = {
    'note': ('info', 'bi-info-circle', 'Note'),
    'warning': ('warning', 'bi-exclamation-triangle', 'Warning'),
    'danger': ('danger', 'bi-x-octagon', 'Danger'),
    'tip': ('success', 'bi-lightbulb', 'Tip'),
    'important': ('primary', 'bi-exclamation-circle', 'Important'),
    'hint': ('secondary', 'bi-question-circle', 'Hint'),
    'caution': ('warning', 'bi-exclamation-diamond', 'Caution'),
    'attention': ('info', 'bi-bell', 'Attention'),
}

# POV (Point of View) block styles - for shared content from friends
POV_STYLES = {
    'pov': ('pov', 'bi-chat-square-quote', None),  # Title comes from the block itself
}


def process_hashtags(text):
    """
    Remove hashtags (#word) from text - they will be displayed separately at the bottom.

    Hashtags are # followed directly by word characters (no space).
    This distinguishes them from Markdown headings which require a space: # Heading
    """
    # Pattern for hashtags: # followed by word characters (letters, numbers, underscore)
    pattern = r'(?<![&\w])#([a-zA-Z][a-zA-Z0-9_]*)\b'

    # Remove hashtags from text (they'll be shown at the bottom)
    return re.sub(pattern, '', text)


def extract_hashtags(text):
    """
    Extract all unique hashtags from text.
    Returns a list of hashtag names (without the # symbol).
    """
    if not text:
        return []

    pattern = r'(?<![&\w])#([a-zA-Z][a-zA-Z0-9_]*)\b'
    matches = re.findall(pattern, text)

    # Return unique hashtags, preserving order of first appearance
    seen = set()
    unique_tags = []
    for tag in matches:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique_tags.append(tag)

    return unique_tags


def process_myst_directives(text):
    """
    Convert MyST-style directives to HTML admonitions.

    Supports: ```{note}, ```{warning}, ```{tip}, ```{danger}, etc.
    """
    # Pattern for MyST directives: ```{directive}\ncontent\n```
    pattern = r'```\{(\w+)\}\s*\n(.*?)```'

    def replace_directive(match):
        directive_type = match.group(1).lower()
        content = match.group(2).strip()

        if directive_type in DIRECTIVE_STYLES:
            style, icon, title = DIRECTIVE_STYLES[directive_type]
            return f'''<div class="admonition admonition-{directive_type} alert alert-{style}">
<div class="admonition-title"><i class="bi {icon} me-2"></i>{title}</div>
<div class="admonition-content">{content}</div>
</div>'''
        else:
            # Unknown directive - render as a styled block
            return f'''<div class="admonition alert alert-secondary">
<div class="admonition-title">{directive_type.title()}</div>
<div class="admonition-content">{content}</div>
</div>'''

    return re.sub(pattern, replace_directive, text, flags=re.DOTALL)


def process_pov_blocks(text):
    """
    Convert POV blocks to styled HTML (admonition style).

    Handles multiple formats:
    1. Injected POV (new format): ```pov @username\ncontent\n```
    2. Injected POV (old format): ```{pov} @username\ncontent\n```
    3. Author's POV (in author's journal): {pov} @username content {/pov}
    """
    def replace_injected_pov(match):
        username = match.group(1)
        content = match.group(2).strip()
        return f'''<div class="admonition admonition-pov alert alert-pov">
<div class="admonition-title"><i class="bi bi-chat-square-quote me-2"></i>@{username} shared</div>
<div class="admonition-content">{content}</div>
</div>'''

    # Pattern 1a: Injected POV blocks (NEW format): ```pov @username\ncontent\n```
    injected_pattern_new = r'```pov\s+@(\w+)\s*\n(.*?)```'
    text = re.sub(injected_pattern_new, replace_injected_pov, text, flags=re.DOTALL)

    # Pattern 1b: Injected POV blocks (OLD format): ```{pov} @username\ncontent\n```
    # Keep for backward compatibility with existing entries
    injected_pattern_old = r'```\{pov\}\s*@(\w+)\s*\n(.*?)```'
    text = re.sub(injected_pattern_old, replace_injected_pov, text, flags=re.DOTALL)

    # Pattern 2: Author's POV blocks with closing tag: {pov} username(s)\ncontent\n{/pov}
    # Usernames can be with or without @ prefix, must be on first line
    author_pattern_closed = r'\{pov\}\s*([^\n]+?)\s*\n(.*?)\{/pov\}'

    def replace_author_pov(match):
        usernames_str = match.group(1).strip()
        content = match.group(2).strip()
        # Extract usernames (with or without @ prefix)
        usernames = re.findall(r'@?([\w]+)', usernames_str)
        recipients = ', '.join(f'@{u}' for u in usernames)
        return f'''<div class="admonition admonition-pov-author alert alert-pov-author">
<div class="admonition-title"><i class="bi bi-send me-2"></i>Shared with {recipients}</div>
<div class="admonition-content">{content}</div>
</div>'''

    text = re.sub(author_pattern_closed, replace_author_pov, text, flags=re.DOTALL | re.IGNORECASE)

    # Pattern 3: Author's POV blocks without closing tag: {pov} username(s)\ncontent (until blank line)
    author_pattern_open = r'\{pov\}\s*([^\n]+?)\s*\n([^\n]*(?:\n(?!\n|\{pov\})[^\n]*)*)'

    text = re.sub(author_pattern_open, replace_author_pov, text, flags=re.IGNORECASE)

    return text


def process_goal_habit_blocks(text):
    """
    Convert {goal} and {habit} blocks to styled HTML.

    Format: {goal} [Title](/goals/1/) - optional note {/goal}
    Format: {habit} [Name](/habits/1/) - Checked in! {/habit}
    """
    def convert_markdown_links(content):
        """Convert [text](url) to <a href="url">text</a>"""
        return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', content)

    # Pattern for goal blocks: {goal} content {/goal}
    goal_pattern = r'\{goal\}\s*(.*?)\s*\{/goal\}'

    def replace_goal(match):
        content = convert_markdown_links(match.group(1).strip())
        return f'''<div class="tracker-block tracker-goal">
<i class="bi bi-bullseye me-2"></i>{content}
</div>'''

    text = re.sub(goal_pattern, replace_goal, text, flags=re.DOTALL | re.IGNORECASE)

    # Pattern for habit blocks: {habit} content {/habit}
    habit_pattern = r'\{habit\}\s*(.*?)\s*\{/habit\}'

    def replace_habit(match):
        content = convert_markdown_links(match.group(1).strip())
        return f'''<div class="tracker-block tracker-habit">
<i class="bi bi-repeat me-2"></i>{content}
</div>'''

    text = re.sub(habit_pattern, replace_habit, text, flags=re.DOTALL | re.IGNORECASE)

    # Also handle old blockquote format for backward compatibility
    def replace_old_goal(match):
        content = convert_markdown_links(match.group(1).strip())
        return f'<div class="tracker-block tracker-goal"><i class="bi bi-bullseye me-2"></i>{content}</div>'

    old_goal_pattern = r'^>\s*\*\*Goal:\*\*\s*(.+?)(?:\s*#goals)?\s*$'
    text = re.sub(old_goal_pattern, replace_old_goal, text, flags=re.MULTILINE)

    def replace_old_habit(match):
        content = convert_markdown_links(match.group(1).strip())
        return f'<div class="tracker-block tracker-habit"><i class="bi bi-repeat me-2"></i>{content}</div>'

    old_habit_pattern = r'^>\s*\*\*Habit:\*\*\s*(.+?)(?:\s*#habits)?\s*$'
    text = re.sub(old_habit_pattern, replace_old_habit, text, flags=re.MULTILINE)

    return text


@register.filter(name='render_markdown')
def render_markdown(value):
    """
    Render Markdown content to HTML with MyST directive support.

    Supports MyST-compatible syntax including:
    - Headers (# ## ###)
    - Bold, italic, strikethrough
    - Lists (ordered and unordered)
    - Code blocks with syntax highlighting
    - Blockquotes
    - Links and images
    - Tables
    - MyST directives: ```{note}, ```{warning}, ```{tip}, etc.
    - Hashtags: #tag (converted to styled spans)
    """
    if not value:
        return ''

    # First, process hashtags before markdown conversion
    # This prevents #word from being interpreted as a heading
    value = process_hashtags(value)

    # Process POV blocks (shared content from friends)
    value = process_pov_blocks(value)

    # Process goal and habit blocks
    value = process_goal_habit_blocks(value)

    # Then, process MyST directives before markdown conversion
    value = process_myst_directives(value)

    # Configure markdown extensions
    extensions = [
        'markdown.extensions.fenced_code',  # ```code blocks```
        'markdown.extensions.codehilite',   # Syntax highlighting
        'markdown.extensions.tables',        # Tables
        'markdown.extensions.nl2br',         # Newlines to <br>
        'markdown.extensions.sane_lists',    # Better list handling
        'markdown.extensions.smarty',        # Smart quotes
        'markdown.extensions.toc',           # Table of contents
    ]

    extension_configs = {
        'markdown.extensions.codehilite': {
            'css_class': 'highlight',
            'guess_lang': True,
        },
    }

    # Convert markdown to HTML
    md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    html = md.convert(value)

    # Sanitize HTML to prevent XSS (but allow our admonition divs)
    allowed_tags = ALLOWED_TAGS + ['i']
    allowed_attrs = dict(ALLOWED_ATTRIBUTES)
    allowed_attrs['i'] = ['class']

    clean_html = bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )

    return mark_safe(clean_html)


@register.filter(name='render_markdown_safe')
def render_markdown_safe(value):
    """
    Render Markdown without sanitization (for trusted content only).
    """
    if not value:
        return ''

    extensions = [
        'markdown.extensions.fenced_code',
        'markdown.extensions.codehilite',
        'markdown.extensions.tables',
        'markdown.extensions.nl2br',
        'markdown.extensions.sane_lists',
        'markdown.extensions.smarty',
    ]

    md = markdown.Markdown(extensions=extensions)
    html = md.convert(value)

    return mark_safe(html)


@register.filter(name='get_hashtags')
def get_hashtags(value):
    """
    Extract hashtags from content for display at the bottom of entry.
    Returns a list of unique hashtag names.
    """
    return extract_hashtags(value)


@register.filter(name='replace')
def replace(value, arg):
    """
    Replace occurrences of a string with another string.
    Usage: {{ value|replace:"search:replacement" }}
    """
    if not value or not arg:
        return value
    try:
        search, replacement = arg.split(':', 1)
        return value.replace(search, replacement)
    except ValueError:
        return value


@register.filter(name='mul')
def multiply(value, arg):
    """
    Multiply a value by the argument.
    Usage: {{ value|mul:100 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value
