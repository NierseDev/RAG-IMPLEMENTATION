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
        
        const sizeMap = {
            small: '16px',
            medium: '24px',
            large: '40px'
        };
        
        spinner.style.cssText = `
            display: inline-block;
            width: ${sizeMap[size]};
            height: ${sizeMap[size]};
            border: 2px solid #f3f3f3;
            border-top: 2px solid ${color};
            border-radius: 50%;
            animation: spin 1s linear infinite;
        `;
        
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
        
        const colors = {
            success: { bg: '#d5f4e6', border: '#27ae60', text: '#1e7e4f' },
            error: { bg: '#fadbd8', border: '#e74c3c', text: '#c0392b' },
            warning: { bg: '#feebc8', border: '#f39c12', text: '#d68910' },
            info: { bg: '#d6eaf8', border: '#3498db', text: '#2471a3' }
        };
        
        const color = colors[type] || colors.info;
        
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            min-width: 300px;
            max-width: 500px;
            padding: 16px 20px;
            background: ${color.bg};
            border-left: 4px solid ${color.border};
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            color: ${color.text};
            font-size: 14px;
            font-weight: 500;
            z-index: 10000;
            animation: slideInRight 0.3s ease-out;
        `;
        
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
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            animation: fadeIn 0.2s;
        `;
        
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'modal-dialog';
        modal.style.cssText = `
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow: hidden;
            animation: scaleIn 0.2s;
        `;
        
        // Modal header
        const header = document.createElement('div');
        header.style.cssText = `
            padding: 20px;
            border-bottom: 1px solid #e1e8ed;
            font-size: 18px;
            font-weight: 600;
            color: #2c3e50;
        `;
        header.textContent = title;
        
        // Modal body
        const body = document.createElement('div');
        body.style.cssText = `
            padding: 20px;
            overflow-y: auto;
            max-height: 400px;
            font-size: 14px;
            color: #2c3e50;
        `;
        
        if (typeof content === 'string') {
            body.innerHTML = content;
        } else {
            body.appendChild(content);
        }
        
        // Modal footer
        const footer = document.createElement('div');
        footer.style.cssText = `
            padding: 15px 20px;
            border-top: 1px solid #e1e8ed;
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        `;
        
        const buttonStyle = `
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s;
        `;
        
        if (showCancel) {
            const cancelBtn = document.createElement('button');
            cancelBtn.textContent = cancelText;
            cancelBtn.style.cssText = buttonStyle + `
                background: #ecf0f1;
                color: #2c3e50;
            `;
            cancelBtn.onclick = () => {
                if (onCancel) onCancel();
                hide();
            };
            footer.appendChild(cancelBtn);
        }
        
        const confirmBtn = document.createElement('button');
        confirmBtn.textContent = confirmText;
        confirmBtn.style.cssText = buttonStyle + `
            background: #3498db;
            color: white;
        `;
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
        
        const colors = {
            success: { bg: '#d5f4e6', text: '#22543d' },
            error: { bg: '#fed7d7', text: '#742a2a' },
            warning: { bg: '#feebc8', text: '#744210' },
            info: { bg: '#d6eaf8', text: '#2471a3' },
            neutral: { bg: '#e2e8f0', text: '#4a5568' }
        };
        
        const color = colors[type] || colors.neutral;
        
        badge.style.cssText = `
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
            background: ${color.bg};
            color: ${color.text};
        `;
        
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
            content: `<p style="margin: 0;">${message}</p>`,
            confirmText: 'Confirm',
            cancelText: 'Cancel',
            onConfirm,
            onCancel,
            showCancel: true
        });
        
        modal.show();
    }
}

// Add CSS animations to document
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    
    @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; }
    }
    
    @keyframes scaleIn {
        from {
            transform: scale(0.9);
            opacity: 0;
        }
        to {
            transform: scale(1);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);

// Export for ES6 modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UIComponents;
}
