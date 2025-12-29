/* ==========================================================================
   Modal Utilities - Modal and overlay handling
   ========================================================================== */

/**
 * Show a confirmation modal
 * @param {object} options - Modal options
 * @param {string} options.title - Modal title
 * @param {string} options.message - Modal message
 * @param {string} options.confirmText - Confirm button text
 * @param {string} options.cancelText - Cancel button text
 * @param {string} options.type - Modal type: danger, warning, success, info
 * @param {Function} options.onConfirm - Callback when confirmed
 * @param {Function} options.onCancel - Callback when cancelled
 */
function showConfirmModal(options) {
    const defaults = {
        title: 'Confirm',
        message: 'Are you sure?',
        confirmText: 'Confirm',
        cancelText: 'Cancel',
        type: 'danger',
        onConfirm: null,
        onCancel: null
    };

    const opts = { ...defaults, ...options };

    const iconMap = {
        danger: 'exclamation-triangle',
        warning: 'exclamation-circle',
        success: 'check-circle',
        info: 'info-circle'
    };

    const colorMap = {
        danger: '#dc2626',
        warning: '#d97706',
        success: '#16a34a',
        info: '#2563eb'
    };

    const bgColorMap = {
        danger: '#fee2e2',
        warning: '#fef3c7',
        success: '#dcfce7',
        info: '#dbeafe'
    };

    // Create overlay
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay active';
    overlay.innerHTML = `
        <div class="modal-content">
            <div class="confirm-modal-icon ${opts.type}">
                <i class="bi bi-${iconMap[opts.type]}" style="color: ${colorMap[opts.type]}; font-size: 1.5rem;"></i>
            </div>
            <h5 class="text-center mb-3">${opts.title}</h5>
            <p class="text-center text-muted mb-4">${opts.message}</p>
            <div class="d-flex gap-3 justify-content-center">
                <button class="btn btn-secondary cancel-btn">${opts.cancelText}</button>
                <button class="btn btn-${opts.type} confirm-btn">${opts.confirmText}</button>
            </div>
        </div>
    `;

    // Apply icon background
    overlay.querySelector('.confirm-modal-icon').style.background = bgColorMap[opts.type];

    document.body.appendChild(overlay);

    // Event handlers
    const closeModal = () => {
        overlay.remove();
    };

    overlay.querySelector('.cancel-btn').addEventListener('click', () => {
        closeModal();
        if (opts.onCancel) opts.onCancel();
    });

    overlay.querySelector('.confirm-btn').addEventListener('click', () => {
        closeModal();
        if (opts.onConfirm) opts.onConfirm();
    });

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeModal();
            if (opts.onCancel) opts.onCancel();
        }
    });

    // Close on Escape
    const handleEscape = (e) => {
        if (e.key === 'Escape') {
            closeModal();
            if (opts.onCancel) opts.onCancel();
            document.removeEventListener('keydown', handleEscape);
        }
    };
    document.addEventListener('keydown', handleEscape);
}

/**
 * Show delete confirmation modal
 * @param {object} options - Options
 * @param {string} options.itemName - Name of item being deleted
 * @param {Function} options.onConfirm - Callback when delete is confirmed
 */
function showDeleteModal(options) {
    showConfirmModal({
        title: 'Delete ' + (options.itemName || 'Item'),
        message: `Are you sure you want to delete this ${options.itemName || 'item'}? This action cannot be undone.`,
        confirmText: 'Delete',
        cancelText: 'Cancel',
        type: 'danger',
        onConfirm: options.onConfirm,
        onCancel: options.onCancel
    });
}

/**
 * Show a simple alert modal
 * @param {string} title - Modal title
 * @param {string} message - Modal message
 * @param {string} type - Alert type: success, danger, warning, info
 */
function showAlertModal(title, message, type = 'info') {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay active';

    const iconMap = {
        danger: 'exclamation-triangle',
        warning: 'exclamation-circle',
        success: 'check-circle',
        info: 'info-circle'
    };

    overlay.innerHTML = `
        <div class="modal-content" style="max-width: 350px;">
            <div class="text-center mb-3">
                <i class="bi bi-${iconMap[type]} text-${type}" style="font-size: 3rem;"></i>
            </div>
            <h5 class="text-center mb-2">${title}</h5>
            <p class="text-center text-muted mb-4">${message}</p>
            <div class="text-center">
                <button class="btn btn-${type} px-4 close-btn">OK</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    const closeModal = () => overlay.remove();

    overlay.querySelector('.close-btn').addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal();
    });
}

/**
 * Initialize custom delete modal overlays
 * Used for entry list delete buttons
 */
function initDeleteModals() {
    document.querySelectorAll('[data-delete-modal]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const itemName = btn.dataset.itemName || 'item';
            const deleteUrl = btn.dataset.deleteUrl;
            const csrfToken = btn.dataset.csrfToken ||
                             document.querySelector('[name=csrfmiddlewaretoken]')?.value;

            showDeleteModal({
                itemName: itemName,
                onConfirm: () => {
                    if (deleteUrl && csrfToken) {
                        const form = document.createElement('form');
                        form.method = 'POST';
                        form.action = deleteUrl;
                        form.innerHTML = `<input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken}">`;
                        document.body.appendChild(form);
                        form.submit();
                    }
                }
            });
        });
    });
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', initDeleteModals);
