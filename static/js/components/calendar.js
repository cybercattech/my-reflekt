/* ==========================================================================
   Calendar Component - Interactive calendar for journal entries
   ========================================================================== */

/**
 * Calendar component class
 */
class JournalCalendar {
    constructor(container, options = {}) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)
            : container;

        if (!this.container) {
            console.error('Calendar container not found');
            return;
        }

        this.options = {
            entryDates: options.entryDates || [],
            onDateSelect: options.onDateSelect || null,
            onMonthChange: options.onMonthChange || null,
            highlightToday: options.highlightToday !== false,
            ...options
        };

        this.currentDate = new Date();
        this.selectedDate = null;

        this.init();
    }

    init() {
        this.render();
        this.attachEvents();
    }

    render() {
        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();
        const today = new Date();

        const monthNames = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ];

        // Get first day of month and total days
        const firstDay = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();

        // Build calendar HTML
        let html = `
            <div class="calendar-header">
                <div class="calendar-title">
                    <h3>${monthNames[month]} ${year}</h3>
                </div>
                <div class="calendar-nav">
                    <button class="calendar-nav-btn" data-action="prev">
                        <i class="bi bi-chevron-left"></i>
                    </button>
                    <button class="calendar-nav-btn" data-action="next">
                        <i class="bi bi-chevron-right"></i>
                    </button>
                </div>
            </div>
            <div class="calendar-weekdays">
                ${['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
                    .map(d => `<span>${d}</span>`).join('')}
            </div>
            <div class="calendar-days">
        `;

        // Add empty cells for days before first of month
        for (let i = 0; i < firstDay; i++) {
            html += '<div class="calendar-day other-month"></div>';
        }

        // Add days of month
        for (let day = 1; day <= daysInMonth; day++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const isToday = this.options.highlightToday &&
                           day === today.getDate() &&
                           month === today.getMonth() &&
                           year === today.getFullYear();
            const hasEntry = this.options.entryDates.includes(dateStr);

            const classes = ['calendar-day'];
            if (isToday) classes.push('today');
            if (hasEntry) classes.push('has-entry');

            html += `
                <div class="${classes.join(' ')}" data-date="${dateStr}">
                    ${day}
                </div>
            `;
        }

        html += '</div>';

        this.container.innerHTML = html;
    }

    attachEvents() {
        // Navigation buttons
        this.container.querySelectorAll('.calendar-nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = btn.dataset.action;
                if (action === 'prev') {
                    this.currentDate.setMonth(this.currentDate.getMonth() - 1);
                } else if (action === 'next') {
                    this.currentDate.setMonth(this.currentDate.getMonth() + 1);
                }
                this.render();
                this.attachEvents();

                if (this.options.onMonthChange) {
                    this.options.onMonthChange(this.currentDate);
                }
            });
        });

        // Day clicks
        this.container.querySelectorAll('.calendar-day:not(.other-month)').forEach(day => {
            day.addEventListener('click', () => {
                const dateStr = day.dataset.date;
                if (dateStr && this.options.onDateSelect) {
                    this.selectedDate = dateStr;
                    this.options.onDateSelect(dateStr);
                }
            });
        });
    }

    /**
     * Update entry dates
     * @param {Array} dates - Array of date strings (YYYY-MM-DD)
     */
    setEntryDates(dates) {
        this.options.entryDates = dates;
        this.render();
        this.attachEvents();
    }

    /**
     * Navigate to a specific month
     * @param {number} year
     * @param {number} month - 0-indexed
     */
    goToMonth(year, month) {
        this.currentDate = new Date(year, month, 1);
        this.render();
        this.attachEvents();
    }

    /**
     * Get the current displayed month
     * @returns {object} { year, month }
     */
    getCurrentMonth() {
        return {
            year: this.currentDate.getFullYear(),
            month: this.currentDate.getMonth()
        };
    }
}

/**
 * Initialize calendar with data from data attributes
 * @param {HTMLElement} container - Container element with data-* attributes
 */
function initCalendarFromData(container) {
    const entryDates = JSON.parse(container.dataset.entryDates || '[]');
    const filterUrl = container.dataset.filterUrl;

    return new JournalCalendar(container, {
        entryDates: entryDates,
        onDateSelect: (dateStr) => {
            if (filterUrl) {
                window.location.href = `${filterUrl}?date=${dateStr}`;
            }
        }
    });
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { JournalCalendar, initCalendarFromData };
}
