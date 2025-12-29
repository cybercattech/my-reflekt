/* ==========================================================================
   Base JavaScript - Global utilities for Reflekt application
   ========================================================================== */

/**
 * Initialize all base functionality when DOM is ready
 */
document.addEventListener('DOMContentLoaded', function() {
    initToastNotifications();
    initPovBadgeUpdater();
    initFeedbackForm();
});

/* ==========================================================================
   Toast Notifications
   ========================================================================== */

/**
 * Auto-dismiss toast notifications after a delay
 */
function initToastNotifications() {
    document.querySelectorAll('.toast-alert').forEach(function(toast) {
        setTimeout(function() {
            toast.classList.add('hiding');
            setTimeout(function() {
                toast.remove();
            }, 300);
        }, 2500);
    });
}

/**
 * Programmatically show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - The type: success, error, warning, info
 */
function showToast(message, type = 'info') {
    const container = document.querySelector('.toast-container') || createToastContainer();

    const iconMap = {
        'success': 'check-circle',
        'error': 'exclamation-circle',
        'danger': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };

    const toast = document.createElement('div');
    toast.className = `toast-alert alert-${type} d-flex align-items-center justify-content-between`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <span><i class="bi bi-${iconMap[type] || 'info-circle'} me-2"></i>${message}</span>
        <button type="button" class="btn-close ms-2" onclick="this.parentElement.remove()"></button>
    `;

    container.appendChild(toast);

    // Auto-dismiss
    setTimeout(function() {
        toast.classList.add('hiding');
        setTimeout(function() {
            toast.remove();
        }, 300);
    }, 2500);
}

/**
 * Create toast container if it doesn't exist
 */
function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
}

/* ==========================================================================
   POV Badge Updater
   ========================================================================== */

/**
 * Initialize POV badge updater if user is authenticated
 */
function initPovBadgeUpdater() {
    const badge = document.getElementById('povBadge');
    const povUrl = badge?.closest('[data-pov-url]')?.dataset.povUrl ||
                   document.body.dataset.povUrl;

    if (!badge || !povUrl) return;

    // Initial check
    updatePovBadge(badge, povUrl);

    // Periodic refresh every minute
    setInterval(() => updatePovBadge(badge, povUrl), 60000);
}

/**
 * Fetch and update the POV badge count
 * @param {HTMLElement} badge - The badge element
 * @param {string} url - The URL to fetch unread count
 */
function updatePovBadge(badge, url) {
    fetch(url)
        .then(r => r.json())
        .then(data => {
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.classList.remove('d-none');
            } else {
                badge.classList.add('d-none');
            }
        })
        .catch(() => {});
}

/* ==========================================================================
   Feedback Form Handler
   ========================================================================== */

/**
 * Initialize the feedback form modal
 */
function initFeedbackForm() {
    const modal = document.getElementById('feedbackModal');
    if (!modal) return;

    const form = document.getElementById('feedbackForm');
    const successDiv = document.getElementById('feedbackSuccess');
    const footer = document.getElementById('feedbackFooter');
    const submitBtn = document.getElementById('submitFeedback');
    const feedbackUrl = modal.dataset.feedbackUrl;
    const csrfToken = modal.dataset.csrfToken || document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    if (!feedbackUrl || !csrfToken) return;

    // Set page URL when modal opens
    modal.addEventListener('show.bs.modal', function() {
        const pageUrlInput = document.getElementById('feedbackPageUrl');
        if (pageUrlInput) {
            pageUrlInput.value = window.location.href;
        }
        // Reset form state
        form.classList.remove('d-none');
        successDiv.classList.add('d-none');
        footer.classList.remove('d-none');
        form.reset();
    });

    // Handle submit
    submitBtn.addEventListener('click', async function() {
        const subject = document.getElementById('feedbackSubject').value.trim();
        const message = document.getElementById('feedbackMessage').value.trim();
        const feedbackType = document.querySelector('input[name="feedbackType"]:checked')?.value;
        const pageUrl = document.getElementById('feedbackPageUrl')?.value;

        if (!subject || !message) {
            alert('Please fill in both subject and details.');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Sending...';

        try {
            const response = await fetch(feedbackUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    type: feedbackType,
                    subject: subject,
                    message: message,
                    page_url: pageUrl
                })
            });

            const data = await response.json();

            if (data.success) {
                form.classList.add('d-none');
                footer.classList.add('d-none');
                successDiv.classList.remove('d-none');
                // Auto-close after 2 seconds
                setTimeout(() => {
                    const bsModal = bootstrap.Modal.getInstance(modal);
                    if (bsModal) bsModal.hide();
                }, 2000);
            } else {
                alert(data.error || 'Something went wrong. Please try again.');
            }
        } catch (error) {
            alert('Failed to submit feedback. Please try again.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="bi bi-send me-1"></i>Send Feedback';
        }
    });
}

/* ==========================================================================
   Utility Functions
   ========================================================================== */

/**
 * Format a number with commas
 * @param {number} num - The number to format
 * @returns {string} Formatted number string
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Truncate text to a specified length
 * @param {string} text - The text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text
 */
function truncateText(text, maxLength = 50) {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength - 3) + '...';
}

/**
 * Debounce function for rate-limiting
 * @param {Function} func - The function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Format date to locale string
 * @param {Date|string} date - Date to format
 * @param {object} options - Intl.DateTimeFormat options
 * @returns {string} Formatted date string
 */
function formatDate(date, options = {}) {
    const d = typeof date === 'string' ? new Date(date) : date;
    const defaultOptions = { year: 'numeric', month: 'short', day: 'numeric' };
    return d.toLocaleDateString('en-US', { ...defaultOptions, ...options });
}
