"""
Parser for importing journal entries from various formats.
Supports Diarly, Day One, and generic markdown exports.
"""
import re
from datetime import datetime, date
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ParsedEntry:
    """Represents a parsed journal entry."""
    entry_date: date
    title: str
    content: str
    tags: List[str]
    location: Optional[str] = None


def parse_diarly_format(text: str) -> List[ParsedEntry]:
    """
    Parse Diarly export format.

    Format example:
        Date:    December 5, 2019 at 12:00:00 AM EST
    # December 05, 2019
    Year: 2019
    Date: December 5, 2019

    Content here...

    #tag1 #tag2
    """
    entries = []

    # Split by the date header pattern
    # Looking for tab or spaces before "Date:" followed by tab or spaces
    # Handles both "    Date:    " (spaces) and "\tDate:\t" (tabs)
    entry_splits = re.split(r'\n[\t ]+Date:[\t ]+', text)

    # Also try splitting from the start if the file begins with the date pattern
    if len(entry_splits) == 1:
        # Try alternate pattern - maybe file starts with Date:
        entry_splits = re.split(r'^[\t ]+Date:[\t ]+', text, flags=re.MULTILINE)

    if len(entry_splits) == 1:
        # Still no luck, try just Date: at start of line
        entry_splits = re.split(r'\nDate:[\t ]+', text)

    for i, chunk in enumerate(entry_splits):
        if i == 0 and not chunk.strip():
            continue  # Skip empty first chunk

        if not chunk.strip():
            continue

        try:
            entry = parse_single_diarly_entry(chunk, i == 0)
            if entry:
                entries.append(entry)
        except Exception as e:
            print(f"Error parsing entry chunk: {e}")
            continue

    return entries


def parse_single_diarly_entry(chunk: str, is_first: bool = False) -> Optional[ParsedEntry]:
    """Parse a single entry from Diarly format."""
    lines = chunk.strip().split('\n')

    if not lines:
        return None

    # First line should be the date (unless it's the first chunk which might have Date: prefix)
    date_line = lines[0].strip()

    # Try to parse the date
    entry_date = parse_date_string(date_line)
    if not entry_date:
        # Maybe the date is in a different format, try to find it
        for line in lines[:5]:
            if 'Date:' in line or re.match(r'^[A-Z][a-z]+ \d+, \d{4}', line.strip()):
                entry_date = parse_date_string(line)
                if entry_date:
                    break

    if not entry_date:
        return None

    # Find the title (usually the markdown heading)
    title = ""
    content_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('# '):
            title = stripped[2:].strip()
            content_start = i + 1
            break

    # Skip metadata lines (Year:, Date:, Weather:, Moon phase:, etc.)
    while content_start < len(lines):
        line = lines[content_start].strip()
        if (line.startswith('Year:') or
            line.startswith('Date:') or
            line.startswith('Weather:') or
            line.startswith('Moon phase:') or
            not line):
            content_start += 1
        else:
            break

    # Get the content
    content_lines = lines[content_start:]

    # Extract tags from content (hashtags at the end)
    tags = []
    content_text = '\n'.join(content_lines)

    # Find hashtags (but not image URLs or markdown links)
    tag_matches = re.findall(r'(?:^|\s)#([a-zA-Z][a-zA-Z0-9_]*)', content_text)
    tags = list(set(tag_matches))

    # Remove standalone tag lines from end of content
    while content_lines and re.match(r'^#[a-zA-Z]', content_lines[-1].strip()):
        content_lines.pop()

    # Extract location if present (Diarly format: [Location Name](diarly://map/...))
    location = None
    location_match = re.search(r'\[([^\]]+)\]\(diarly://map/', content_text)
    if location_match:
        location = location_match.group(1)

    # Clean up content - remove Diarly-specific links
    content_text = '\n'.join(content_lines)
    content_text = re.sub(r'\[([^\]]+)\]\(diarly://[^\)]+\)', r'\1', content_text)

    # Clean up empty lines at start/end
    content_text = content_text.strip()

    if not title:
        title = entry_date.strftime('%B %d, %Y')

    return ParsedEntry(
        entry_date=entry_date,
        title=title,
        content=content_text,
        tags=tags,
        location=location
    )


def parse_date_string(date_str: str) -> Optional[date]:
    """Parse various date string formats."""
    date_str = date_str.strip()

    # Remove "Date:" prefix if present
    if date_str.startswith('Date:'):
        date_str = date_str[5:].strip()

    # Common formats to try
    formats = [
        '%B %d, %Y at %I:%M:%S %p %Z',  # December 5, 2019 at 12:00:00 AM EST
        '%B %d, %Y at %I:%M:%S %p',      # December 5, 2019 at 12:00:00 AM
        '%B %d, %Y',                      # December 5, 2019
        '%B %d, %Y',                      # December 05, 2019
        '%Y-%m-%d',                       # 2019-12-05
        '%m/%d/%Y',                       # 12/05/2019
        '%d/%m/%Y',                       # 05/12/2019
    ]

    # Strip timezone abbreviation if present (EST, PST, etc.)
    date_str = re.sub(r'\s+[A-Z]{2,4}$', '', date_str)

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.date()
        except ValueError:
            continue

    # Try to extract just the date part
    match = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', date_str)
    if match:
        try:
            dt = datetime.strptime(match.group(1), '%B %d, %Y')
            return dt.date()
        except ValueError:
            pass

    return None


def parse_generic_markdown(text: str) -> List[ParsedEntry]:
    """
    Parse generic markdown journal format.
    Assumes entries are separated by horizontal rules (---) or date headings.
    """
    entries = []

    # Try splitting by horizontal rules first
    chunks = re.split(r'\n---+\n', text)

    if len(chunks) <= 1:
        # Try splitting by date headings (# followed by date)
        chunks = re.split(r'\n(?=# [A-Z][a-z]+ \d{1,2}, \d{4})', text)

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        # Look for a date in the first few lines
        lines = chunk.split('\n')
        entry_date = None
        title = ""
        content_start = 0

        for i, line in enumerate(lines[:5]):
            stripped = line.strip()

            # Check for markdown heading with date
            if stripped.startswith('# '):
                potential_title = stripped[2:].strip()
                parsed_date = parse_date_string(potential_title)
                if parsed_date:
                    entry_date = parsed_date
                    title = potential_title
                    content_start = i + 1
                    break
                else:
                    title = potential_title

            # Check for date on its own line
            parsed_date = parse_date_string(stripped)
            if parsed_date:
                entry_date = parsed_date
                content_start = i + 1

        if not entry_date:
            continue  # Skip entries without a date

        content = '\n'.join(lines[content_start:]).strip()

        # Extract tags
        tag_matches = re.findall(r'(?:^|\s)#([a-zA-Z][a-zA-Z0-9_]*)', content)
        tags = list(set(tag_matches))

        if not title:
            title = entry_date.strftime('%B %d, %Y')

        entries.append(ParsedEntry(
            entry_date=entry_date,
            title=title,
            content=content,
            tags=tags
        ))

    return entries


def parse_import_file(content: str, format_hint: str = 'auto') -> List[ParsedEntry]:
    """
    Main entry point for parsing import files.

    Args:
        content: The text content of the file
        format_hint: 'diarly', 'markdown', or 'auto' for auto-detection

    Returns:
        List of ParsedEntry objects
    """
    if format_hint == 'auto':
        # Auto-detect format
        if '    Date:    ' in content or 'diarly://' in content:
            format_hint = 'diarly'
        else:
            format_hint = 'markdown'

    if format_hint == 'diarly':
        return parse_diarly_format(content)
    else:
        return parse_generic_markdown(content)
