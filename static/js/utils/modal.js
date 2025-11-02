/**
 * Modal Manager Utility
 * Centralized modal system for alerts, confirmations, and prompts
 * 
 * Features:
 * - Custom styled modals with Font Awesome icons
 * - XSS protection via HTML escaping
 * - Support for alert, confirm, and prompt dialogs
 * - Unique modal IDs to prevent conflicts
 * 
 * Dependencies:
 * - Font Awesome icons (https://fontawesome.com/)
 * - Modal CSS classes (.modal, .modal-content, .modal-header, .modal-body, .modal-footer)
 */

(function(window) {
    'use strict';

    /**
     * HTML escape utility to prevent XSS attacks
     * @param {string} text - Text to escape
     * @returns {string} HTML-escaped text
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * ModalManager - Centralized modal system
     */
    const ModalManager = {
        /**
         * Show a custom alert modal
         * @param {string} title - Modal title
         * @param {string} message - Modal message
         * @param {string} type - Modal type: 'success', 'error', or 'info' (default)
         * @param {function} callback - Optional callback function when OK is clicked
         */
        alert: function(title, message, type = 'info', callback) {
            const iconClass = type === 'success' ? 'fa-check-circle' : 
                            type === 'error' ? 'fa-exclamation-circle' : 
                            'fa-info-circle';
            const iconColor = type === 'success' ? '#4CAF50' : 
                            type === 'error' ? '#FF5252' : 
                            '#20B2AA';
            
            const modalHTML = `
                <div id="customAlertModal" class="modal" style="display: flex;">
                    <div class="modal-content" style="max-width: 400px;">
                        <div class="modal-header">
                            <h3><i class="fas ${iconClass}" style="color: ${iconColor};"></i> ${escapeHtml(title)}</h3>
                            <button class="modal-close" onclick="ModalManager.closeModal('customAlertModal')">&times;</button>
                        </div>
                        <div class="modal-body">
                            <p style="color: #CCC; margin: 0; line-height: 1.5;">${escapeHtml(message)}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-primary" onclick="ModalManager.closeModal('customAlertModal')">
                                <i class="fas fa-check"></i> OK
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            const existingModal = document.getElementById('customAlertModal');
            if (existingModal) existingModal.remove();
            
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            
            if (callback) {
                const modal = document.getElementById('customAlertModal');
                const okBtn = modal.querySelector('.btn-primary');
                okBtn.onclick = function() {
                    ModalManager.closeModal('customAlertModal');
                    callback();
                };
            }
        },
        
        /**
         * Show an alert modal with trusted HTML content (USE CAREFULLY - only for internal trusted content)
         * @param {string} title - Modal title (will be escaped)
         * @param {string} htmlMessage - HTML message content (NOT escaped - must be trusted)
         * @param {string} type - Modal type: 'success', 'error', or 'info' (default)
         * @param {function} callback - Optional callback function when OK is clicked
         * 
         * WARNING: Only use this for internally-generated HTML content. NEVER pass user input directly.
         */
        alertHtml: function(title, htmlMessage, type = 'info', callback) {
            const iconClass = type === 'success' ? 'fa-check-circle' : 
                            type === 'error' ? 'fa-exclamation-circle' : 
                            'fa-info-circle';
            const iconColor = type === 'success' ? '#4CAF50' : 
                            type === 'error' ? '#FF5252' : 
                            '#20B2AA';
            
            const modalHTML = `
                <div id="customAlertModal" class="modal" style="display: flex;">
                    <div class="modal-content" style="max-width: 500px;">
                        <div class="modal-header">
                            <h3><i class="fas ${iconClass}" style="color: ${iconColor};"></i> ${escapeHtml(title)}</h3>
                            <button class="modal-close" onclick="ModalManager.closeModal('customAlertModal')">&times;</button>
                        </div>
                        <div class="modal-body">
                            <div style="color: #CCC; line-height: 1.5;">${htmlMessage}</div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-primary" onclick="ModalManager.closeModal('customAlertModal')">
                                <i class="fas fa-check"></i> OK
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            const existingModal = document.getElementById('customAlertModal');
            if (existingModal) existingModal.remove();
            
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            
            if (callback) {
                const modal = document.getElementById('customAlertModal');
                const okBtn = modal.querySelector('.btn-primary');
                okBtn.onclick = function() {
                    ModalManager.closeModal('customAlertModal');
                    callback();
                };
            }
        },
        
        /**
         * Show a confirm modal (Promise-based for async/await)
         * @param {string} title - Modal title
         * @param {string} message - Modal message
         * @param {string|function} onConfirm - Confirm button text (string) or legacy callback (function)
         * @param {string|function} onCancel - Cancel button text (string) or legacy callback (function)
         * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
         */
        confirm: function(title, message, onConfirm, onCancel) {
            return new Promise((resolve) => {
                const confirmText = typeof onConfirm === 'string' ? onConfirm : 'Confirm';
                const cancelText = typeof onCancel === 'string' ? onCancel : 'Cancel';
                const confirmCallback = typeof onConfirm === 'function' ? onConfirm : null;
                const cancelCallback = typeof onCancel === 'function' ? onCancel : null;
                
                // Handler for all cancellation paths
                const handleCancel = function() {
                    ModalManager.closeModal('customConfirmModal');
                    if (cancelCallback) cancelCallback();
                    resolve(false);
                };
                
                const modalHTML = `
                    <div id="customConfirmModal" class="modal" style="display: flex;">
                        <div class="modal-content" style="max-width: 450px;">
                            <div class="modal-header">
                                <h3>${escapeHtml(title)}</h3>
                                <button class="modal-close" id="confirmCloseBtn">&times;</button>
                            </div>
                            <div class="modal-body">
                                <div style="color: #CCC; line-height: 1.5;">${escapeHtml(message)}</div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" id="confirmCancelBtn">
                                    <i class="fas fa-times"></i> ${escapeHtml(cancelText)}
                                </button>
                                <button type="button" class="btn btn-primary" id="confirmOkBtn">
                                    <i class="fas fa-check"></i> ${escapeHtml(confirmText)}
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                
                const existingModal = document.getElementById('customConfirmModal');
                if (existingModal) existingModal.remove();
                
                document.body.insertAdjacentHTML('beforeend', modalHTML);
                
                document.getElementById('confirmOkBtn').onclick = function() {
                    ModalManager.closeModal('customConfirmModal');
                    if (confirmCallback) confirmCallback();
                    resolve(true);
                };
                
                document.getElementById('confirmCancelBtn').onclick = handleCancel;
                document.getElementById('confirmCloseBtn').onclick = handleCancel;
                
                const modal = document.getElementById('customConfirmModal');
                modal.onclick = function(e) {
                    if (e.target === modal) {
                        handleCancel();
                    }
                };
            });
        },
        
        /**
         * Show a confirm modal with trusted HTML content (Promise-based for async/await)
         * @param {string} title - Modal title (supports HTML)
         * @param {string} htmlMessage - HTML message content (NOT escaped - must be trusted)
         * @param {string|function} onConfirm - Confirm button text (string) or legacy callback (function)
         * @param {string|function} onCancel - Cancel button text (string) or legacy callback (function)
         * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
         * 
         * WARNING: Only use this for internally-generated HTML content. NEVER pass user input directly.
         */
        confirmHtml: function(title, htmlMessage, onConfirm, onCancel) {
            return new Promise((resolve) => {
                const confirmText = typeof onConfirm === 'string' ? onConfirm : 'Confirm';
                const cancelText = typeof onCancel === 'string' ? onCancel : 'Cancel';
                const confirmCallback = typeof onConfirm === 'function' ? onConfirm : null;
                const cancelCallback = typeof onCancel === 'function' ? onCancel : null;
                
                // Handler for all cancellation paths
                const handleCancel = function() {
                    ModalManager.closeModal('customConfirmModal');
                    if (cancelCallback) cancelCallback();
                    resolve(false);
                };
                
                const modalHTML = `
                    <div id="customConfirmModal" class="modal" style="display: flex;">
                        <div class="modal-content" style="max-width: 550px;">
                            <div class="modal-header">
                                <h3>${title}</h3>
                                <button class="modal-close" id="confirmCloseBtn">&times;</button>
                            </div>
                            <div class="modal-body">
                                <div style="color: #CCC; line-height: 1.5;">${htmlMessage}</div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" id="confirmCancelBtn">
                                    <i class="fas fa-times"></i> ${escapeHtml(cancelText)}
                                </button>
                                <button type="button" class="btn btn-primary" id="confirmOkBtn">
                                    <i class="fas fa-check"></i> ${escapeHtml(confirmText)}
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                
                const existingModal = document.getElementById('customConfirmModal');
                if (existingModal) existingModal.remove();
                
                document.body.insertAdjacentHTML('beforeend', modalHTML);
                
                document.getElementById('confirmOkBtn').onclick = function() {
                    ModalManager.closeModal('customConfirmModal');
                    if (confirmCallback) confirmCallback();
                    resolve(true);
                };
                
                document.getElementById('confirmCancelBtn').onclick = handleCancel;
                document.getElementById('confirmCloseBtn').onclick = handleCancel;
                
                const modal = document.getElementById('customConfirmModal');
                modal.onclick = function(e) {
                    if (e.target === modal) {
                        handleCancel();
                    }
                };
            });
        },
        
        /**
         * Show a prompt modal
         * @param {string} title - Modal title
         * @param {string} message - Modal message
         * @param {string} defaultValue - Default value for the input
         * @param {function} onSubmit - Callback function when submitted (receives input value)
         * @param {function} onCancel - Optional callback function when cancelled
         * @param {string} placeholder - Input placeholder text (default: 'Enter your input here...')
         */
        prompt: function(title, message, defaultValue, onSubmit, onCancel, placeholder = 'Enter your input here...') {
            const modalHTML = `
                <div id="customPromptModal" class="modal" style="display: flex;">
                    <div class="modal-content" style="max-width: 500px;">
                        <div class="modal-header">
                            <h3>${escapeHtml(title)}</h3>
                            <button class="modal-close" onclick="ModalManager.closeModal('customPromptModal')">&times;</button>
                        </div>
                        <div class="modal-body">
                            <p style="color: #CCC; margin-bottom: 1rem; line-height: 1.5;">${escapeHtml(message)}</p>
                            <input type="text" id="promptInput" class="form-control" 
                                   value="${escapeHtml(defaultValue || '')}" 
                                   placeholder="${escapeHtml(placeholder)}"
                                   style="width: 100%;">
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" id="promptCancelBtn">
                                <i class="fas fa-times"></i> Cancel
                            </button>
                            <button type="button" class="btn btn-primary" id="promptSubmitBtn">
                                <i class="fas fa-check"></i> Submit
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            const existingModal = document.getElementById('customPromptModal');
            if (existingModal) existingModal.remove();
            
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            
            const input = document.getElementById('promptInput');
            setTimeout(() => {
                input.focus();
                input.select();
            }, 100);
            
            const submitHandler = function() {
                const value = document.getElementById('promptInput').value;
                ModalManager.closeModal('customPromptModal');
                if (onSubmit) onSubmit(value);
            };
            
            document.getElementById('promptSubmitBtn').onclick = submitHandler;
            
            input.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    submitHandler();
                }
            });
            
            document.getElementById('promptCancelBtn').onclick = function() {
                ModalManager.closeModal('customPromptModal');
                if (onCancel) onCancel();
            };
        },
        
        /**
         * Close a modal by ID
         * @param {string} modalId - The ID of the modal to close
         */
        closeModal: function(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.style.display = 'none';
                setTimeout(() => modal.remove(), 300);
            }
        },

        /**
         * Utility: Expose escapeHtml for external use
         * @param {string} text - Text to escape
         * @returns {string} HTML-escaped text
         */
        escapeHtml: escapeHtml
    };

    // Export ModalManager to global scope
    window.ModalManager = ModalManager;

})(window);
