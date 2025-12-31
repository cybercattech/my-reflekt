# Reflekt Project Standards

This document outlines the coding standards, conventions, and patterns for the Reflekt journaling application. **Always consult this document before making changes.**

## Multi-Tenant Architecture

- This is a multi-tenant dashboard where multiple clients can login and see their data
- Client 1 data should NEVER mix with client 2 data
- Always filter queries by `user=request.user`

---

## CSS Standards

### No Inline CSS in HTML Templates

**NEVER put CSS in HTML template files.** All styles must go in dedicated CSS files under `static/css/`.

```
static/css/
├── base.css                    # Global styles, variables, common elements
├── layouts/
│   ├── global.css              # Body layout, sticky footer, navbar
│   ├── sidebar-unified.css     # Sidebar navigation styles
│   ├── sidebar.css             # Legacy sidebar styles
│   └── dashboard.css           # Dashboard layout styles
├── pages/
│   ├── journal.css             # Journal/Insights page styles
│   ├── analytics.css           # Analytics pages styles
│   ├── goals.css               # Goals page styles
│   └── habits.css              # Habits page styles
└── components/
    ├── cards.css               # Card component styles
    ├── badges.css              # Badge styles
    ├── buttons.css             # Button styles
    ├── forms.css               # Form styles
    └── modals.css              # Modal styles
```

### Including CSS in Templates

```django
{% load static %}

{% block extra_css %}
<link href="{% static 'css/pages/journal.css' %}" rel="stylesheet">
{% endblock %}
```

### CSS Variables (Custom Properties)

Always use the defined CSS variables for consistency:

```css
:root {
    --primary-color: #4f46e5;      /* Indigo - main brand color */
    --secondary-color: #7c3aed;    /* Purple - accent color */
    --navbar-height: 56px;
    --footer-height: 50px;
    --sidebar-left-width: 240px;
    --sidebar-right-width: 280px;
}
```

---

## JavaScript Standards

### No Inline JavaScript in HTML Templates

**NEVER put JavaScript in HTML template files** except for:
1. Essential page-specific initialization that requires template variables
2. CSRF token access

For page-specific JS that needs template data, minimize inline code:

```django
{% block extra_js %}
<script>
// Only template variable initialization
const ENTRY_DATES = new Set([{% for date in dates %}'{{ date }}',{% endfor %}]);
</script>
<script src="{% static 'js/pages/journal.js' %}"></script>
{% endblock %}
```

### JavaScript File Structure

```
static/js/
├── base.js                     # Global utilities
├── pages/
│   ├── journal.js              # Journal page logic
│   └── analytics.js            # Analytics page logic
└── components/
    ├── calendar.js             # Calendar component
    └── charts.js               # Chart configurations
```

---

## Bootstrap Usage

### Version
- Bootstrap 5.3.2 (via CDN)
- Bootstrap Icons 1.11.1

### Standard Classes

**Spacing (padding/margin):**
- Use Bootstrap's spacing utilities: `p-1` through `p-5`, `m-1` through `m-5`
- Standard page padding: `py-4` on container
- Card padding: `p-3` or `p-4`
- Gap between elements: `gap-2` or `gap-3`

**Border Radius:**
- Small elements: `rounded` or `rounded-pill`
- Cards: `rounded-3` (12px) or `rounded-4` (16px)
- Custom cards use: `border-radius: 16px`

**Shadows:**
- Light shadow: `shadow-sm`
- Medium shadow: `shadow`
- Custom cards: `box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08)`
- Hover shadow: `box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12)`

**Buttons:**
- Primary: `btn btn-primary`
- Outline: `btn btn-outline-secondary`
- Rounded pills: `btn btn-primary rounded-pill px-4`
- Small: `btn btn-sm`

---

## Color Palette

### Brand Colors
```css
--primary-color: #4f46e5;      /* Indigo */
--secondary-color: #7c3aed;    /* Purple */
```

### Gradient Cards
```css
/* Purple gradient (streaks, prompts) */
background: linear-gradient(135deg, #4c1d95 0%, #7c3aed 50%, #a855f7 100%);

/* Indigo gradient (entries) */
background: linear-gradient(135deg, #818cf8 0%, #6366f1 100%);

/* Teal gradient (devotion) */
background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);

/* Red gradient (words) */
background: linear-gradient(135deg, #f87171 0%, #dc2626 100%);

/* Pink gradient (journaled) */
background: linear-gradient(135deg, #be185d 0%, #9f1239 100%);

/* Navy gradient (places) */
background: linear-gradient(135deg, #334155 0%, #1e293b 100%);
```

### Text Colors
```css
/* Headings */
color: #1f2937;    /* gray-800 */

/* Body text */
color: #374151;    /* gray-700 */

/* Muted text */
color: #6b7280;    /* gray-500 */

/* Very muted */
color: #9ca3af;    /* gray-400 */
```

### Status Colors
```css
/* Success */
background: #dcfce7; color: #166534; border: #bbf7d0;

/* Error */
background: #fee2e2; color: #991b1b; border: #fecaca;

/* Warning */
background: #fef3c7; color: #92400e; border: #fde68a;

/* Info */
background: #dbeafe; color: #1e40af; border: #bfdbfe;
```

---

## Card Styles

### Standard Insight Card
```css
.insight-card {
    background: white;
    border-radius: 16px;
    padding: 1.25rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    transition: all 0.2s;
}

.insight-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    transform: translateY(-2px);
}
```

### Entry Card
```css
.entry-card {
    border: none;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    background: white;
}
```

---

## Layout Standards

### Page Structure
```html
{% extends 'base.html' %}
{% load static %}

{% block extra_css %}
<link href="{% static 'css/pages/pagename.css' %}" rel="stylesheet">
{% endblock %}

{% block content %}
<div class="container-fluid py-4">
    <!-- Page content -->
</div>
{% endblock %}

{% block extra_js %}
<script src="{% static 'js/pages/pagename.js' %}"></script>
{% endblock %}
```

### Sidebar Layout
- Sidebar width: 260px (desktop), 240px (medium), hidden on mobile
- Main content offset: `margin-left: 260px` when authenticated
- Footer offset: same as main content

---

## Responsive Breakpoints

Follow Bootstrap 5 breakpoints:
```css
/* Extra small (default) */
/* Small: 576px */
@media (min-width: 576px) { }

/* Medium: 768px */
@media (max-width: 768px) { }

/* Large: 992px */
@media (max-width: 992px) { }

/* Extra large: 1200px */
@media (max-width: 1200px) { }
```

### Grid Responsive Patterns
```css
/* 5 columns -> 3 -> 2 -> 2 */
.streaks-grid {
    grid-template-columns: repeat(5, 1fr);
}
@media (max-width: 1200px) {
    .streaks-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 992px) {
    .streaks-grid { grid-template-columns: repeat(2, 1fr); }
}
```

---

## Template Conventions

### Template Tags to Load
```django
{% load static %}           # For static files
{% load humanize %}          # For number formatting (intcomma, naturaltime)
{% load tz %}                # For timezone handling
{% load subscription_tags %} # For user_is_premium checks
{% load challenge_tags %}    # For challenge widgets
```

### Conditional Sidebar Class
```django
<main class="main-content {% if user.is_authenticated %}main-content-with-sidebar{% endif %}">
```

### Premium Feature Check
```django
{% if user|user_is_premium %}
    <!-- Premium content -->
{% else %}
    <span class="badge bg-warning text-dark">PRO</span>
{% endif %}
```

---

## Icons

Use Bootstrap Icons exclusively:
```html
<i class="bi bi-journal-text"></i>
<i class="bi bi-gear"></i>
<i class="bi bi-plus-lg"></i>
```

Common icons:
- Journal: `bi-journal-text`, `bi-book`
- Settings: `bi-gear`
- Add: `bi-plus-lg`, `bi-plus-circle`
- Edit: `bi-pencil`
- Delete: `bi-trash`
- Calendar: `bi-calendar`, `bi-calendar-event`
- User: `bi-person`, `bi-people`
- Analytics: `bi-graph-up`, `bi-bar-chart`

---

## Third-Party Libraries

### Included via CDN
- Bootstrap 5.3.2 (CSS + JS)
- Bootstrap Icons 1.11.1
- Chart.js (for charts)
- Leaflet 1.9.4 (for maps)
- HTMX 1.9.10 (for dynamic updates)
- EasyMDE (markdown editor)
- Quill (rich text editor)

### Loading Order
1. Bootstrap CSS
2. Bootstrap Icons
3. Page-specific CSS
4. Custom CSS files
5. Bootstrap JS (bundle)
6. Third-party JS libraries
7. Custom JS files

---

## Forms

### Standard Form Structure
```html
<form method="post" class="needs-validation" novalidate>
    {% csrf_token %}
    <div class="mb-3">
        <label for="field" class="form-label">Label</label>
        <input type="text" class="form-control" id="field" name="field" required>
        <div class="invalid-feedback">Error message</div>
    </div>
    <button type="submit" class="btn btn-primary">Submit</button>
</form>
```

### Form Sizing
- Standard inputs: default size
- Compact forms: `form-control-sm`, `btn-sm`
- Large forms: `form-control-lg`

---

## File Naming Conventions

### Templates
- Use snake_case: `entry_list.html`, `entry_detail.html`
- Partials start with underscore: `_sidebar.html`, `_navbar.html`
- Located in: `templates/appname/`

### Static Files
- CSS: `static/css/pages/pagename.css`
- JS: `static/js/pages/pagename.js`
- Images: `static/images/`

### Django Apps
- Located in: `apps/appname/`
- Models, views, urls follow Django conventions

---

## Performance Considerations

1. Use CSS file caching (Django's staticfiles)
2. Minimize DOM manipulation in JavaScript
3. Use HTMX for partial page updates when appropriate
4. Lazy load images and maps
5. Use Chart.js with `maintainAspectRatio: false` for responsive charts

---

## Accessibility

1. Always use semantic HTML (`<main>`, `<nav>`, `<article>`, etc.)
2. Include `aria-label` on icon-only buttons
3. Ensure sufficient color contrast
4. Use `alt` text on images
5. Support keyboard navigation

---

## Security

1. Always use `{% csrf_token %}` in forms
2. Filter all queries by authenticated user
3. Never trust client-side data
4. Sanitize user input before rendering
5. Use Django's built-in XSS protection
