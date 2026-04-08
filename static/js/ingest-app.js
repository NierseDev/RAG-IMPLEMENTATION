/**
 * Document Ingestion Application
 * Handles file upload, processing, and document management
 */

class IngestApp {
    constructor() {
        this.documents = [];
        this.uploadQueue = [];
        this.isUploading = false;
        this.stats = null;
        this.duplicateMode = 'skip'; // skip, replace, append
        
        this.init();
    }

    async init() {
        this.bindElements();
        this.attachEventListeners();
        await this.loadDocuments();
        await this.refreshStats();
        
        // Auto-refresh every 5 seconds
        setInterval(() => this.refreshDocuments(), 5000);
        setInterval(() => this.refreshStats(), 10000);
    }

    bindElements() {
        // Upload elements
        this.uploadBoxEl = document.getElementById('uploadBox');
        this.fileInputEl = document.getElementById('fileInput');
        this.browseBtnEl = document.getElementById('browseBtn');
        this.duplicateModeEl = document.getElementById('duplicateMode');
        
        // Document table
        this.docTableBodyEl = document.getElementById('docTableBody');
        
        // Stats elements (will be in right panel)
    }

    attachEventListeners() {
        // File input
        this.fileInputEl.addEventListener('change', (e) => this.handleFiles(e.target.files));
        this.browseBtnEl.addEventListener('click', () => this.fileInputEl.click());
        
        // Drag and drop
        this.uploadBoxEl.addEventListener('click', () => this.fileInputEl.click());
        this.uploadBoxEl.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadBoxEl.classList.add('dragover');
        });
        this.uploadBoxEl.addEventListener('dragleave', () => {
            this.uploadBoxEl.classList.remove('dragover');
        });
        this.uploadBoxEl.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadBoxEl.classList.remove('dragover');
            this.handleFiles(e.dataTransfer.files);
        });
        
        // Duplicate mode
        if (this.duplicateModeEl) {
            this.duplicateModeEl.addEventListener('change', (e) => {
                this.duplicateMode = e.target.value;
            });
        }
    }

    // ==================== FILE UPLOAD ====================

    handleFiles(files) {
        if (!files || files.length === 0) return;
        
        const fileArray = Array.from(files);
        const validFiles = fileArray.filter(file => this.isValidFile(file));
        
        if (validFiles.length === 0) {
            this.showError('No valid files selected. Supported formats: PDF, DOCX, PPTX, HTML, MD, TXT');
            return;
        }

        validFiles.forEach(file => {
            this.uploadQueue.push(file);
        });

        this.processUploadQueue();
    }

    isValidFile(file) {
        const validExtensions = ['.pdf', '.docx', '.pptx', '.html', '.htm', '.md', '.txt'];
        const fileName = file.name.toLowerCase();
        return validExtensions.some(ext => fileName.endsWith(ext));
    }

    async processUploadQueue() {
        if (this.isUploading || this.uploadQueue.length === 0) return;
        
        this.isUploading = true;
        
        while (this.uploadQueue.length > 0) {
            const file = this.uploadQueue.shift();
            await this.uploadFile(file);
        }
        
        this.isUploading = false;
        await this.loadDocuments();
    }

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('duplicate_mode', this.duplicateMode);

        try {
            // Show upload progress
            this.showUploadProgress(file.name);

            const response = await fetch('/ingest/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                this.showSuccess(`✓ ${file.name} uploaded successfully`);
                
                // Check if it was a duplicate
                if (data.duplicate_action) {
                    this.showInfo(`Duplicate handled: ${data.duplicate_action}`);
                }
            } else {
                this.showError(`✗ ${file.name}: ${data.detail || 'Upload failed'}`);
            }

        } catch (error) {
            console.error('Upload error:', error);
            this.showError(`✗ ${file.name}: Network error`);
        } finally {
            this.hideUploadProgress();
        }
    }

    showUploadProgress(filename) {
        const progressEl = document.getElementById('uploadProgress');
        if (progressEl) {
            progressEl.textContent = `Uploading: ${filename}...`;
            progressEl.style.display = 'block';
        }
    }

    hideUploadProgress() {
        const progressEl = document.getElementById('uploadProgress');
        if (progressEl) {
            progressEl.style.display = 'none';
        }
    }

    // ==================== DOCUMENT MANAGEMENT ====================

    async loadDocuments() {
        try {
            const response = await fetch('/ingest/documents?page=1&page_size=100');
            const data = await response.json();
            
            this.documents = data.documents || [];
            this.renderDocuments();
        } catch (error) {
            console.error('Failed to load documents:', error);
        }
    }

    async refreshDocuments() {
        // Silently refresh without error messages
        try {
            const response = await fetch('/ingest/documents?page=1&page_size=100');
            const data = await response.json();
            
            this.documents = data.documents || [];
            this.renderDocuments();
        } catch (error) {
            // Silently fail
        }
    }

    renderDocuments() {
        if (this.documents.length === 0) {
            this.docTableBodyEl.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; padding: 40px; color: #95a5a6;">
                        <div style="font-size: 48px; margin-bottom: 10px;">📄</div>
                        <div>No documents uploaded yet</div>
                    </td>
                </tr>
            `;
            return;
        }

        this.docTableBodyEl.innerHTML = this.documents.map(doc => `
            <tr>
                <td>
                    <div class="doc-name">
                        ${this.getFileIcon(doc.filename)} ${this.escapeHtml(doc.filename)}
                    </div>
                </td>
                <td>${this.formatFileSize(doc.file_size)}</td>
                <td>${this.formatDate(doc.upload_date)}</td>
                <td>${doc.chunk_count || 0}</td>
                <td>${this.renderStatusBadge(doc.status)}</td>
                <td>
                    <button class="action-btn view-btn" onclick="ingestApp.viewDocument(${doc.id})" title="View Details">
                        👁️
                    </button>
                    <button class="action-btn delete-btn" onclick="ingestApp.deleteDocument(${doc.id})" title="Delete">
                        🗑️
                    </button>
                </td>
            </tr>
        `).join('');
    }

    renderStatusBadge(status) {
        const badges = {
            'processing': '<span class="status-badge status-processing">⏳ Processing</span>',
            'completed': '<span class="status-badge status-completed">✓ Completed</span>',
            'failed': '<span class="status-badge status-failed">✗ Failed</span>'
        };
        return badges[status] || '<span class="status-badge">Unknown</span>';
    }

    getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const icons = {
            'pdf': '📕',
            'docx': '📘',
            'doc': '📘',
            'pptx': '📙',
            'ppt': '📙',
            'html': '🌐',
            'htm': '🌐',
            'md': '📝',
            'txt': '📄'
        };
        return icons[ext] || '📄';
    }

    async viewDocument(docId) {
        try {
            const response = await fetch(`/ingest/documents/${docId}`);
            const data = await response.json();
            
            const details = `
                <div style="text-align: left;">
                    <h3>${this.escapeHtml(data.filename)}</h3>
                    <hr style="margin: 10px 0;">
                    <p><strong>Status:</strong> ${data.status}</p>
                    <p><strong>Size:</strong> ${this.formatFileSize(data.file_size)}</p>
                    <p><strong>Chunks:</strong> ${data.chunk_count}</p>
                    <p><strong>Upload Date:</strong> ${new Date(data.upload_date).toLocaleString()}</p>
                    <p><strong>Hash:</strong> <code>${data.file_hash}</code></p>
                    ${data.error_message ? `<p style="color: #e74c3c;"><strong>Error:</strong> ${this.escapeHtml(data.error_message)}</p>` : ''}
                </div>
            `;
            
            if (window.UIComponents) {
                UIComponents.createModal({
                    title: 'Document Details',
                    content: details,
                    showCancel: false
                });
            } else {
                alert(details.replace(/<[^>]*>/g, ''));
            }
        } catch (error) {
            console.error('Failed to view document:', error);
            this.showError('Failed to load document details');
        }
    }

    async deleteDocument(docId) {
        const confirmed = window.UIComponents 
            ? await new Promise(resolve => {
                UIComponents.confirm(
                    'Delete this document? This will also remove all associated chunks.',
                    () => resolve(true),
                    () => resolve(false)
                );
            })
            : confirm('Delete this document? This will also remove all associated chunks.');

        if (!confirmed) return;

        try {
            const response = await fetch(`/ingest/documents/${docId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.showSuccess('Document deleted successfully');
                await this.loadDocuments();
                await this.refreshStats();
            } else {
                const data = await response.json();
                this.showError(`Failed to delete: ${data.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Delete error:', error);
            this.showError('Failed to delete document');
        }
    }

    // ==================== STATISTICS ====================

    async refreshStats() {
        try {
            const response = await fetch('/database/status');
            const data = await response.json();
            
            this.stats = data;
            this.renderStats(data);
        } catch (error) {
            console.error('Failed to refresh stats:', error);
        }
    }

    renderStats(data) {
        const stats = data.statistics || {};
        const docStats = stats.document_status || {};
        
        // Update stat cards
        this.updateStatCard('totalDocs', stats.total_documents || 0);
        this.updateStatCard('totalChunks', stats.total_chunks || 0);
        this.updateStatCard('completedDocs', docStats.completed || 0);
        this.updateStatCard('processingDocs', docStats.processing || 0);
    }

    updateStatCard(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    // ==================== UTILITIES ====================

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString();
    }

    showSuccess(message) {
        if (window.UIComponents) {
            UIComponents.showToast(message, 'success');
        } else {
            console.log('Success:', message);
        }
    }

    showError(message) {
        if (window.UIComponents) {
            UIComponents.showToast(message, 'error');
        } else {
            console.error('Error:', message);
        }
    }

    showInfo(message) {
        if (window.UIComponents) {
            UIComponents.showToast(message, 'info');
        } else {
            console.log('Info:', message);
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.ingestApp = new IngestApp();
});
