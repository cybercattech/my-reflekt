/* ==========================================================================
   Navigation Components - Sidebar toggle and navigation utilities
   ========================================================================== */

/**
 * Initialize dashboard sidebar toggle for mobile
 */
function initSidebarToggle() {
    const toggleBtn = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.dashboard-sidebar');
    const backdrop = document.querySelector('.sidebar-backdrop');

    if (!toggleBtn || !sidebar) return;

    // Create backdrop if it doesn't exist
    let backdropEl = backdrop;
    if (!backdropEl) {
        backdropEl = document.createElement('div');
        backdropEl.className = 'sidebar-backdrop';
        document.body.appendChild(backdropEl);
    }

    // Toggle sidebar
    toggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('show');
        backdropEl.classList.toggle('show');

        // Update toggle icon
        const icon = toggleBtn.querySelector('i');
        if (icon) {
            icon.className = sidebar.classList.contains('show')
                ? 'bi bi-x-lg'
                : 'bi bi-list';
        }
    });

    // Close on backdrop click
    backdropEl.addEventListener('click', () => {
        sidebar.classList.remove('show');
        backdropEl.classList.remove('show');

        const icon = toggleBtn.querySelector('i');
        if (icon) icon.className = 'bi bi-list';
    });

    // Close on nav link click (mobile)
    sidebar.querySelectorAll('.sidebar-nav-link').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 991.98) {
                sidebar.classList.remove('show');
                backdropEl.classList.remove('show');

                const icon = toggleBtn.querySelector('i');
                if (icon) icon.className = 'bi bi-list';
            }
        });
    });
}

/**
 * Initialize insights sidebar toggle (collapsible)
 */
function initInsightsSidebarToggle() {
    const toggleBtn = document.querySelector('.insights-toggle');
    const sidebar = document.querySelector('.insights-sidebar-right');
    const content = document.querySelector('.insights-content');

    if (!toggleBtn || !sidebar || !content) return;

    toggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        content.style.display = sidebar.classList.contains('collapsed') ? 'none' : 'block';
    });
}

/**
 * Set active nav item based on current URL
 */
function setActiveNavItem() {
    const currentPath = window.location.pathname;

    document.querySelectorAll('.sidebar-nav-link, .nav-link-item').forEach(link => {
        const href = link.getAttribute('href');
        if (href && currentPath.startsWith(href)) {
            link.classList.add('active');
        }
    });
}

/**
 * Smooth scroll to anchor links
 */
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;

            const target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

/**
 * Initialize all navigation components
 */
function initNavigation() {
    initSidebarToggle();
    initInsightsSidebarToggle();
    setActiveNavItem();
    initSmoothScroll();
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', initNavigation);

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initSidebarToggle,
        initInsightsSidebarToggle,
        setActiveNavItem,
        initSmoothScroll,
        initNavigation
    };
}
