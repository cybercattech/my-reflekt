/* ==========================================================================
   Chart.js Utilities - Shared chart configurations and helpers
   ========================================================================== */

/**
 * Default chart color palette
 */
const CHART_COLORS = {
    primary: '#6366f1',
    secondary: '#8b5cf6',
    success: '#22c55e',
    danger: '#ef4444',
    warning: '#f59e0b',
    info: '#0ea5e9',
    muted: '#6b7280',
    white: '#ffffff',
    transparent: 'transparent'
};

/**
 * Mood colors for charts
 */
const MOOD_COLORS = {
    ecstatic: '#a855f7',
    happy: '#22c55e',
    neutral: '#6b7280',
    sad: '#3b82f6',
    angry: '#ef4444'
};

/**
 * Create a gradient for chart backgrounds
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {string} startColor - Start color (top)
 * @param {string} endColor - End color (bottom)
 * @returns {CanvasGradient}
 */
function createChartGradient(ctx, startColor, endColor) {
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, startColor);
    gradient.addColorStop(1, endColor);
    return gradient;
}

/**
 * Default options for line charts
 */
const defaultLineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            display: false
        }
    },
    scales: {
        x: {
            grid: { display: false },
            ticks: { color: '#6b7280' }
        },
        y: {
            grid: { color: '#f3f4f6' },
            ticks: { color: '#6b7280' }
        }
    }
};

/**
 * Default options for bar charts
 */
const defaultBarChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false }
    },
    scales: {
        x: {
            grid: { display: false },
            ticks: { color: '#6b7280' }
        },
        y: {
            grid: { color: '#f3f4f6' },
            ticks: { color: '#6b7280' }
        }
    }
};

/**
 * Default options for doughnut charts
 */
const defaultDoughnutChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            position: 'bottom',
            labels: {
                padding: 10,
                font: { size: 11 }
            }
        }
    }
};

/**
 * Create a bar chart for monthly entries
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Array} data - Monthly data array
 * @param {object} options - Additional options
 * @returns {Chart}
 */
function createEntriesBarChart(canvas, data, options = {}) {
    const ctx = canvas.getContext('2d');
    const currentMonth = new Date().getMonth();

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'],
            datasets: [{
                data: data,
                backgroundColor: data.map((_, i) =>
                    i === currentMonth ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.4)'
                ),
                borderRadius: 4,
                barThickness: 12
            }]
        },
        options: {
            ...defaultBarChartOptions,
            scales: {
                x: {
                    display: true,
                    grid: { display: false },
                    ticks: { color: 'rgba(255,255,255,0.7)', font: { size: 10 } }
                },
                y: {
                    display: true,
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: 'rgba(255,255,255,0.7)', stepSize: 10 }
                }
            },
            ...options
        }
    });
}

/**
 * Create a sentiment trend line chart
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Array} labels - X-axis labels
 * @param {Array} data - Sentiment data
 * @param {object} options - Additional options
 * @returns {Chart}
 */
function createSentimentChart(canvas, labels, data, options = {}) {
    const ctx = canvas.getContext('2d');

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.length ? labels : ['No data'],
            datasets: [{
                label: 'Average Sentiment',
                data: data.length ? data : [0],
                borderColor: 'rgba(255,255,255,0.9)',
                backgroundColor: 'rgba(255,255,255,0.1)',
                fill: true,
                tension: 0.3,
                pointBackgroundColor: 'white',
                pointBorderColor: 'white'
            }]
        },
        options: {
            ...defaultLineChartOptions,
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: 'rgba(255,255,255,0.7)' }
                },
                y: {
                    min: -1,
                    max: 1,
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: {
                        color: 'rgba(255,255,255,0.7)',
                        callback: function(value) {
                            if (value === 0) return 'Neutral';
                            if (value === 1) return 'Positive';
                            if (value === -1) return 'Negative';
                            return value;
                        }
                    }
                }
            },
            ...options
        }
    });
}

/**
 * Create a mood distribution doughnut chart
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {object} moodData - Mood distribution data { mood: count }
 * @param {object} options - Additional options
 * @returns {Chart}
 */
function createMoodDoughnutChart(canvas, moodData, options = {}) {
    const ctx = canvas.getContext('2d');
    const labels = Object.keys(moodData);
    const values = Object.values(moodData);

    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels.map(l => l.charAt(0).toUpperCase() + l.slice(1)),
            datasets: [{
                data: values,
                backgroundColor: labels.map(l => MOOD_COLORS[l] || '#6b7280'),
                borderColor: 'rgba(255,255,255,0.2)',
                borderWidth: 2
            }]
        },
        options: {
            ...defaultDoughnutChartOptions,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: 'rgba(255,255,255,0.9)',
                        padding: 10,
                        font: { size: 11 }
                    }
                }
            },
            ...options
        }
    });
}

/**
 * Update chart data dynamically
 * @param {Chart} chart - Chart instance
 * @param {Array} newData - New data array
 * @param {Array} newLabels - New labels array (optional)
 */
function updateChartData(chart, newData, newLabels = null) {
    chart.data.datasets[0].data = newData;
    if (newLabels) {
        chart.data.labels = newLabels;
    }
    chart.update();
}
