/**
 * Shared UI Components Library
 * Reusable components for the RAG application
 */

class UIComponents {
    /**
     * Create a loading spinner element
     * @param {string} size - Size of spinner: 'small', 'medium', 'large'
     * @param {string} color - Color of spinner (default: '#3498db')
     * @returns {HTMLElement} Spinner element
     */
    static createSpinner(size = 'medium', color = '#3498db') {
        const spinner = document.createElement('div');
        spinner.className = `spinner spinner-${size}`;
        spinner.style.setProperty('--spinner-color', color);
        
        return spinner;
    }
    
    /**
     * Create and show a toast notification
     * @param {string} message - Notification message
     * @param {string} type - Type: 'success', 'error', 'warning', 'info'
     * @param {number} duration - Duration in ms (default: 3000)
     */
    static showToast(message, type = 'info', duration = 3000) {
        // Remove existing toasts
        const existingToasts = document.querySelectorAll('.toast-notification');
        existingToasts.forEach(toast => toast.remove());
        
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        // Auto-remove after duration
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-in';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
    
    /**
     * Create a modal dialog
     * @param {Object} options - Modal options
     * @returns {Object} Modal controller with show/hide methods
     */
    static createModal(options = {}) {
        const {
            title = 'Modal',
            content = '',
            confirmText = 'OK',
            cancelText = 'Cancel',
            onConfirm = null,
            onCancel = null,
            showCancel = true
        } = options;
        
        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'modal-dialog';
        
        // Modal header
        const header = document.createElement('div');
        header.className = 'modal-header';
        header.textContent = title;
        
        // Modal body
        const body = document.createElement('div');
        body.className = 'modal-body';
        
        if (typeof content === 'string') {
            body.innerHTML = content;
        } else {
            body.appendChild(content);
        }
        
        // Modal footer
        const footer = document.createElement('div');
        footer.className = 'modal-footer';
        
        if (showCancel) {
            const cancelBtn = document.createElement('button');
            cancelBtn.textContent = cancelText;
            cancelBtn.className = 'modal-button modal-button--secondary';
            cancelBtn.onclick = () => {
                if (onCancel) onCancel();
                hide();
            };
            footer.appendChild(cancelBtn);
        }
        
        const confirmBtn = document.createElement('button');
        confirmBtn.textContent = confirmText;
        confirmBtn.className = 'modal-button modal-button--primary';
        confirmBtn.onclick = () => {
            if (onConfirm) onConfirm();
            hide();
        };
        footer.appendChild(confirmBtn);
        
        modal.appendChild(header);
        modal.appendChild(body);
        modal.appendChild(footer);
        overlay.appendChild(modal);
        
        // Close on overlay click
        overlay.onclick = (e) => {
            if (e.target === overlay) {
                if (onCancel) onCancel();
                hide();
            }
        };
        
        function show() {
            document.body.appendChild(overlay);
        }
        
        function hide() {
            overlay.style.animation = 'fadeOut 0.2s';
            setTimeout(() => overlay.remove(), 200);
        }
        
        return { show, hide, element: modal };
    }
    
    /**
     * Create a status badge
     * @param {string} status - Status text
     * @param {string} type - Type: 'success', 'error', 'warning', 'info', 'neutral'
     * @returns {HTMLElement} Badge element
     */
    static createStatusBadge(status, type = 'neutral') {
        const badge = document.createElement('span');
        badge.className = `status-badge status-${type}`;
        badge.textContent = status;
        
        return badge;
    }
    
    /**
     * Create a confirmation dialog
     * @param {string} message - Confirmation message
     * @param {Function} onConfirm - Callback on confirm
     * @param {Function} onCancel - Callback on cancel
     */
    static confirm(message, onConfirm, onCancel = null) {
        const modal = this.createModal({
            title: 'Confirmation',
            content: `<p class="modal-message">${message}</p>`,
            confirmText: 'Confirm',
            cancelText: 'Cancel',
            onConfirm,
            onCancel,
            showCancel: true
        });
        
        modal.show();
    }
}

// Export for ES6 modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UIComponents;
}
