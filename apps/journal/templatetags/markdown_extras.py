"""
Template filters for rendering Markdown content with MyST directive support.
"""
import re
import markdown
from django import template
from django.utils.safestring import mark_safe
import bleach
from bleach.css_sanitizer import CSSSanitizer

register = template.Library()

# CSS Sanitizer for allowing safe inline styles
css_sanitizer = CSSSanitizer(allowed_css_properties=[
    'max-width', 'max-height', 'width', 'height', 'cursor',
    'margin', 'margin-top', 'margin-bottom', 'margin-left', 'margin-right',
    'padding', 'padding-top', 'padding-bottom', 'padding-left', 'padding-right',
    'text-align', 'float', 'display',
])

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
    'figure', 'figcaption',  # For {image} blocks
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'loading', 'onclick', 'style'],
    'code': ['class'],
    'pre': ['class'],
    'div': ['class'],
    'span': ['class', 'data-tag', 'data-capture-type', 'data-capture-name'],
    'th': ['align'],
    'td': ['align'],
    'figure': ['class'],
    'figcaption': ['class'],
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


def process_inline_markdown(content):
    """
    Process inline markdown (bold, italic, links) within content.
    Used for blocks that are processed before the main markdown conversion.
    """
    # Bold: **text** or __text__
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
    content = re.sub(r'__(.+?)__', r'<strong>\1</strong>', content)

    # Italic: *text* or _text_
    content = re.sub(r'\*([^*]+?)\*', r'<em>\1</em>', content)
    content = re.sub(r'(?<![_\w])_([^_]+?)_(?![_\w])', r'<em>\1</em>', content)

    # Strikethrough: ~~text~~
    content = re.sub(r'~~(.+?)~~', r'<s>\1</s>', content)

    # Inline code: `code`
    content = re.sub(r'`([^`]+?)`', r'<code>\1</code>', content)

    # Links: [text](url)
    content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', content)

    return content


def process_myst_directives(text):
    """
    Convert MyST-style directives to HTML admonitions.

    Supports: ```{note}, ```{warning}, ```{tip}, ```{danger}, etc.
    """
    # Pattern for MyST directives: ```{directive}\ncontent\n```
    pattern = r'```\{(\w+)\}\s*\n(.*?)```'

    def replace_directive(match):
        directive_type = match.group(1).lower()
        content = process_inline_markdown(match.group(2).strip())

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
        content = process_inline_markdown(match.group(2).strip())
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
        content = process_inline_markdown(match.group(2).strip())
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


def process_capture_blocks(text):
    """
    Convert capture blocks like {place}, {travel}, {workout}, etc. to styled HTML badges.

    Format: {place} Central Park (Park) {/place}
    Format: {travel} Car: NYC → Boston {/travel}

    Note: {dream} and {gratitude} are handled separately as admonitions.
    """
    # Capture type configurations: (icon, color_class)
    CAPTURE_STYLES = {
        'place': ('bi-pin-map', 'capture-place'),
        'travel': ('bi-geo-alt', 'capture-travel'),
        'workout': ('bi-heart-pulse', 'capture-workout'),
        'watched': ('bi-film', 'capture-watched'),
        'meal': ('bi-cup-hot', 'capture-meal'),
        'book': ('bi-book', 'capture-book'),
        'person': ('bi-person', 'capture-person'),
    }

    def replace_capture(match):
        capture_type = match.group(1).lower()
        content = match.group(2).strip()

        if capture_type in CAPTURE_STYLES:
            icon, css_class = CAPTURE_STYLES[capture_type]
            # Extract the main name for data attribute (for hover lookups)
            # For place: "Central Park (Park)" -> "Central Park"
            # For travel: "Car: NYC → Boston" -> "Boston" (destination)
            name = content.split('(')[0].strip() if '(' in content else content
            if '→' in name:
                name = name.split('→')[-1].strip()

            return f'<span class="capture-inline {css_class}" data-capture-type="{capture_type}" data-capture-name="{name}"><i class="bi {icon}"></i> {content}</span>'
        else:
            return f'<span class="capture-inline">{content}</span>'

    # Pattern for inline capture blocks (excluding dream and gratitude which are admonitions)
    pattern = r'\{(place|travel|workout|watched|meal|book|person)\}\s*(.*?)\s*\{/\1\}'
    text = re.sub(pattern, replace_capture, text, flags=re.DOTALL | re.IGNORECASE)

    return text


def process_image_blocks(text, attachments=None):
    """
    Convert {image} blocks to inline images.

    Supports multiple formats:

    MyST directive syntax (fenced):
    ```{image} https://example.com/photo.jpg
    :width: 500px
    :alt: My photo
    ```

    Inline syntax:
    - {image} https://example.com/photo.jpg {/image} - Full URL
    - {image} /media/path/to/image.jpg {/image} - Relative URL
    - {image} 1 {/image} - Attachment by position (1-indexed)
    - {image} filename.jpg {/image} - Attachment by filename
    - {image} photo.jpg | My vacation photo {/image} - With alt text
    """
    # Build attachment lookup if provided
    attachment_list = list(attachments) if attachments else []
    attachment_by_name = {a.file_name.lower(): a for a in attachment_list}

    def resolve_image_url(src):
        """Resolve image source to URL, checking attachments if needed."""
        src = src.strip()

        # Check if it's a full URL
        if src.startswith(('http://', 'https://', '//')):
            return src, None
        # Check if it's a relative path starting with /
        elif src.startswith('/'):
            return src, None
        # Check if it's a number (attachment position)
        elif src.isdigit():
            idx = int(src) - 1  # Convert to 0-indexed
            if 0 <= idx < len(attachment_list):
                attachment = attachment_list[idx]
                if attachment.is_image:
                    return attachment.file.url, attachment.file_name
        # Check if it matches an attachment filename
        else:
            src_lower = src.lower()
            if src_lower in attachment_by_name:
                attachment = attachment_by_name[src_lower]
                if attachment.is_image:
                    return attachment.file.url, attachment.file_name

        return None, None

    def build_image_html(image_url, alt_text='', width=None, height=None, align=None):
        """Build the HTML for an image figure."""
        style_parts = ['cursor: pointer;']
        if width:
            style_parts.append(f'max-width: {width};')
        if height:
            style_parts.append(f'max-height: {height};')
        style = ' '.join(style_parts)

        # Escape quotes in alt text for onclick
        alt_escaped = alt_text.replace("'", "\\'").replace('"', '&quot;')

        # Build CSS classes based on alignment
        classes = ['entry-image']
        if align:
            align = align.lower()
            if align == 'left':
                classes.append('entry-image-left')
            elif align == 'right':
                classes.append('entry-image-right')
            elif align == 'center':
                classes.append('entry-image-center')
        class_str = ' '.join(classes)

        return f'<figure class="{class_str}"><img src="{image_url}" alt="{alt_text}" loading="lazy" onclick="openLightbox(\'{image_url}\', \'{alt_escaped}\')" style="{style}"><figcaption>{alt_text}</figcaption></figure>'

    def replace_myst_image(match):
        """Handle MyST directive syntax: ```{image} URL\n:options\n```"""
        first_line = match.group(1).strip()
        options_block = match.group(2) if match.group(2) else ''

        # Parse options from the block
        options = {}
        for line in options_block.strip().split('\n'):
            line = line.strip()
            if line.startswith(':') and ':' in line[1:]:
                # Format is :key: value
                key_end = line.index(':', 1)
                key = line[1:key_end].strip()
                value = line[key_end + 1:].strip()
                options[key] = value

        # Get options
        alt_text = options.get('alt', '')
        width = options.get('width', None)
        height = options.get('height', None)
        align = options.get('align', None)

        # Resolve the image URL
        image_url, filename = resolve_image_url(first_line)

        if not alt_text and filename:
            alt_text = filename

        if image_url:
            return build_image_html(image_url, alt_text, width, height, align)
        else:
            return f'<span class="text-muted"><i class="bi bi-image me-1"></i>[Image: {first_line}]</span>'

    def replace_inline_image(match):
        """Handle inline syntax: {image} content {/image}"""
        content = match.group(1).strip()

        # Check for alt text (separated by |)
        if '|' in content:
            src, alt_text = content.split('|', 1)
            src = src.strip()
            alt_text = alt_text.strip()
        else:
            src = content
            alt_text = ''

        image_url, filename = resolve_image_url(src)

        if not alt_text and filename:
            alt_text = filename

        if image_url:
            return build_image_html(image_url, alt_text)
        else:
            return f'<span class="text-muted"><i class="bi bi-image me-1"></i>[Image: {src}]</span>'

    # Pattern 1: MyST directive syntax ```{image} URL\n:options\n```
    # Allow options with or without trailing newlines before closing ```
    myst_pattern = r'```\{image\}\s*([^\n]+)\n((?::[^\n]+\n?)*)\s*```'
    text = re.sub(myst_pattern, replace_myst_image, text, flags=re.IGNORECASE)

    # Pattern 2: Simple MyST-like syntax without backticks: {image} URL\n:options...
    # This matches: {image} URL followed by optional :key: value lines
    # The block ends at a blank line or non-option line
    simple_myst_pattern = r'\{image\}\s*([^\n]+)\n((?::[^\n]+\n)*)'
    text = re.sub(simple_myst_pattern, replace_myst_image, text, flags=re.IGNORECASE)

    # Pattern 3: Inline syntax {image} content {/image}
    inline_pattern = r'\{image\}\s*(.*?)\s*\{/image\}'
    text = re.sub(inline_pattern, replace_inline_image, text, flags=re.DOTALL | re.IGNORECASE)

    return text


def process_wellness_blocks(text):
    """
    Convert {dream} and {gratitude} blocks to styled admonitions.

    Format: {dream} My dream content... {/dream}
    Format: {gratitude} Things I'm grateful for... {/gratitude}

    These render as full-width admonition boxes, not inline badges.
    """
    # Dream blocks - light blue background (#C3EEFA)
    dream_pattern = r'\{dream\}\s*(.*?)\s*\{/dream\}'

    def replace_dream(match):
        content = process_inline_markdown(match.group(1).strip())
        return f'''<div class="admonition admonition-dream">
<div class="admonition-title"><i class="bi bi-cloud-moon me-2"></i>Dream Journal</div>
<div class="admonition-content">{content}</div>
</div>'''

    text = re.sub(dream_pattern, replace_dream, text, flags=re.DOTALL | re.IGNORECASE)

    # Gratitude blocks - soft pink/warm background
    gratitude_pattern = r'\{gratitude\}\s*(.*?)\s*\{/gratitude\}'

    def replace_gratitude(match):
        content = process_inline_markdown(match.group(1).strip())
        return f'''<div class="admonition admonition-gratitude">
<div class="admonition-title"><i class="bi bi-heart me-2"></i>Gratitude</div>
<div class="admonition-content">{content}</div>
</div>'''

    text = re.sub(gratitude_pattern, replace_gratitude, text, flags=re.DOTALL | re.IGNORECASE)

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

    # Process capture blocks ({place}, {travel}, {workout}, etc.)
    value = process_capture_blocks(value)

    # Process wellness blocks ({dream}, {gratitude}) as admonitions
    value = process_wellness_blocks(value)

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
        css_sanitizer=css_sanitizer,
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


@register.filter(name='render_blog_markdown')
def render_blog_markdown(value):
    """
    Render Markdown for blog posts with MyST directive support.

    Optimized for blog content (no hashtag processing, POV blocks, etc.)
    Supports:
    - All standard Markdown (headers, bold, italic, lists, etc.)
    - Code blocks with syntax highlighting
    - Tables
    - MyST directives: ```{note}, ```{warning}, ```{tip}, ```{danger}, etc.
    - Images and links
    """
    if not value:
        return ''

    # Process MyST directives
    value = process_myst_directives(value)

    # Configure markdown extensions
    extensions = [
        'markdown.extensions.fenced_code',
        'markdown.extensions.codehilite',
        'markdown.extensions.tables',
        'markdown.extensions.nl2br',
        'markdown.extensions.sane_lists',
        'markdown.extensions.smarty',
        'markdown.extensions.toc',
        'markdown.extensions.attr_list',  # For adding classes to elements
        'markdown.extensions.def_list',   # Definition lists
        'markdown.extensions.footnotes',  # Footnotes
        'markdown.extensions.abbr',       # Abbreviations
        'markdown.extensions.md_in_html', # Markdown inside HTML blocks
    ]

    extension_configs = {
        'markdown.extensions.codehilite': {
            'css_class': 'highlight',
            'guess_lang': True,
            'linenums': False,
        },
        'markdown.extensions.toc': {
            'permalink': False,
        },
    }

    # Convert markdown to HTML
    md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    html = md.convert(value)

    # For blog posts (staff-written trusted content), we use minimal sanitization
    # Just ensure no script tags or dangerous attributes
    blog_allowed_tags = ALLOWED_TAGS + [
        'i', 'figure', 'figcaption', 'details', 'summary',
        'dl', 'dt', 'dd', 'abbr', 'mark', 'ins', 'del',
        'section', 'article', 'aside', 'header', 'footer', 'nav',
        'iframe',  # For embedded videos
    ]

    blog_allowed_attrs = dict(ALLOWED_ATTRIBUTES)
    blog_allowed_attrs['i'] = ['class']
    blog_allowed_attrs['div'] = ['class', 'id', 'style']
    blog_allowed_attrs['span'] = ['class', 'id', 'style']
    blog_allowed_attrs['iframe'] = ['src', 'width', 'height', 'frameborder', 'allowfullscreen', 'allow']
    blog_allowed_attrs['*'] = ['class', 'id']

    clean_html = bleach.clean(
        html,
        tags=blog_allowed_tags,
        attributes=blog_allowed_attrs,
        css_sanitizer=css_sanitizer,
        strip=True
    )

    return mark_safe(clean_html)


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


@register.simple_tag
def render_entry_content(entry):
    """
    Render entry content with full support for all block types including images.

    This template tag is used instead of the render_markdown filter when
    we need access to the entry's attachments for {image} blocks.

    Usage: {% render_entry_content entry %}
    """
    if not entry or not entry.content:
        return ''

    value = entry.content

    # Get entry attachments for image block processing
    attachments = entry.attachments.all() if hasattr(entry, 'attachments') else []

    # First, process hashtags before markdown conversion
    value = process_hashtags(value)

    # Process POV blocks (shared content from friends)
    value = process_pov_blocks(value)

    # Process goal and habit blocks
    value = process_goal_habit_blocks(value)

    # Process capture blocks ({place}, {travel}, {workout}, etc.)
    value = process_capture_blocks(value)

    # Process wellness blocks ({dream}, {gratitude}) as admonitions
    value = process_wellness_blocks(value)

    # Process image blocks with attachments
    value = process_image_blocks(value, attachments)

    # Then, process MyST directives before markdown conversion
    value = process_myst_directives(value)

    # Configure markdown extensions
    extensions = [
        'markdown.extensions.fenced_code',
        'markdown.extensions.codehilite',
        'markdown.extensions.tables',
        'markdown.extensions.nl2br',
        'markdown.extensions.sane_lists',
        'markdown.extensions.smarty',
        'markdown.extensions.toc',
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

    # Sanitize HTML to prevent XSS (but allow our custom elements)
    allowed_tags = ALLOWED_TAGS + ['i']
    allowed_attrs = dict(ALLOWED_ATTRIBUTES)
    allowed_attrs['i'] = ['class']

    clean_html = bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        css_sanitizer=css_sanitizer,
        strip=True
    )

    return mark_safe(clean_html)
