/**
 * Chat Application - Main Controller
 * Handles chat history, messaging, debug tools, and API integration
 */

class ChatApp {
    constructor() {
        this.currentSessionId = null;
        this.sessions = [];
        this.messages = [];
        this.isProcessing = false;
        this.agentStatus = null;
        this.dbStatus = null;
        
        this.init();
    }

    async init() {
        this.bindElements();
        this.attachEventListeners();
        await this.loadSessions();
        await this.refreshStatus();
        
        // Auto-refresh status every 10 seconds
        setInterval(() => this.refreshStatus(), 10000);
    }

    bindElements() {
        // Chat history
        this.chatHistoryEl = document.getElementById('chatHistory');
        this.newChatBtn = document.querySelector('.new-chat-btn');
        
        // Chat area
        this.chatMessagesEl = document.getElementById('chatMessages');
        this.chatInputEl = document.getElementById('chatInput');
        this.sendBtn = document.getElementById('sendBtn');
        
        // Debug panels
        this.reasoningTraceEl = document.getElementById('reasoningTrace');
    }

    attachEventListeners() {
        this.newChatBtn.addEventListener('click', () => this.createNewSession());
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        // Auto-resize textarea
        this.chatInputEl.addEventListener('input', (e) => {
            e.target.style.height = 'auto';
            e.target.style.height = (e.target.scrollHeight) + 'px';
        });
        
        // Send on Enter (Shift+Enter for new line)
        this.chatInputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }

    // ==================== SESSION MANAGEMENT ====================

    async loadSessions() {
        try {
            const response = await fetch('/query/sessions');
            const data = await response.json();
            
            this.sessions = data.sessions || [];
            this.renderSessions();
            
            // Load most recent session if available
            if (this.sessions.length > 0 && !this.currentSessionId) {
                await this.loadSession(this.sessions[0].session_id);
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
            this.showError('Failed to load chat history');
        }
    }

    renderSessions() {
        if (this.sessions.length === 0) {
            this.chatHistoryEl.innerHTML = '<p style="color: #95a5a6; font-size: 12px; padding: 10px;">No chat history</p>';
            return;
        }

        this.chatHistoryEl.innerHTML = this.sessions.map(session => `
            <div class="chat-item ${session.session_id === this.currentSessionId ? 'active' : ''}" 
                 data-session-id="${session.session_id}">
                <div class="chat-item-title">${this.escapeHtml(session.title)}</div>
                <div class="chat-item-date">${this.formatDate(session.created_at)}</div>
            </div>
        `).join('');

        // Attach click handlers
        this.chatHistoryEl.querySelectorAll('.chat-item').forEach(item => {
            item.addEventListener('click', () => {
                const sessionId = item.dataset.sessionId;
                this.loadSession(sessionId);
            });
        });
    }

    async createNewSession() {
        try {
            const response = await fetch('/query/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: 'New Chat' })
            });
            
            const data = await response.json();
            this.currentSessionId = data.session_id;
            
            await this.loadSessions();
            this.clearChat();
            this.chatInputEl.focus();
        } catch (error) {
            console.error('Failed to create session:', error);
            this.showError('Failed to create new chat');
        }
    }

    async loadSession(sessionId) {
        try {
            const response = await fetch(`/query/sessions/${sessionId}`);
            const data = await response.json();
            
            this.currentSessionId = sessionId;
            this.messages = data.messages || [];
            this.renderMessages();
            this.renderSessions(); // Re-render to update active state
        } catch (error) {
            console.error('Failed to load session:', error);
            this.showError('Failed to load chat session');
        }
    }

    async deleteSession(sessionId) {
        if (!confirm('Delete this chat session?')) return;
        
        try {
            await fetch(`/query/sessions/${sessionId}`, { method: 'DELETE' });
            
            if (this.currentSessionId === sessionId) {
                this.currentSessionId = null;
                this.clearChat();
            }
            
            await this.loadSessions();
        } catch (error) {
            console.error('Failed to delete session:', error);
            this.showError('Failed to delete chat');
        }
    }

    // ==================== MESSAGING ====================

    async sendMessage() {
        const query = this.chatInputEl.value.trim();
        if (!query || this.isProcessing) return;

        // Create session if needed
        if (!this.currentSessionId) {
            await this.createNewSession();
        }

        this.isProcessing = true;
        this.sendBtn.disabled = true;
        this.chatInputEl.value = '';
        this.chatInputEl.style.height = 'auto';

        // Add user message to UI
        this.addMessage('user', query);

        // Show loading state
        const loadingId = this.addMessage('assistant', '<div class="loading"></div>', true);
        this.reasoningTraceEl.innerHTML = '<p style="color: #95a5a6; font-size: 12px;">Processing query...</p>';

        try {
            const response = await fetch('/query/agentic', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    session_id: this.currentSessionId
                })
            });

            const data = await response.json();

            // Remove loading message
            this.removeMessage(loadingId);

            // Add assistant response
            this.addMessage('assistant', data.answer, false, data);

            // Update reasoning trace
            this.updateReasoningTrace(data.reasoning_trace);

            // Update query stats
            this.updateQueryStats(data);

            // Update session title if it's the first message
            if (this.messages.length === 2) { // user + assistant
                await this.updateSessionTitle(query);
            }

        } catch (error) {
            console.error('Failed to send message:', error);
            this.removeMessage(loadingId);
            this.addMessage('assistant', '❌ Failed to process query. Please try again.');
            this.showError('Failed to send message');
        } finally {
            this.isProcessing = false;
            this.sendBtn.disabled = false;
            this.chatInputEl.focus();
        }
    }

    addMessage(role, content, isLoading = false, metadata = null) {
        const messageId = `msg-${Date.now()}-${Math.random()}`;
        const message = { role, content, timestamp: new Date().toISOString(), metadata };
        
        if (!isLoading) {
            this.messages.push(message);
        }

        // Remove empty state if present
        const emptyState = this.chatMessagesEl.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        const messageEl = document.createElement('div');
        messageEl.className = `message message-${role}`;
        messageEl.id = messageId;
        
        const avatar = role === 'user' ? '👤' : '🤖';
        const roleLabel = role === 'user' ? 'You' : 'Assistant';
        
        messageEl.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-role">${roleLabel}</span>
                    <span class="message-time">${this.formatTime(new Date())}</span>
                </div>
                <div class="message-body">${this.formatMessage(content)}</div>
                ${metadata && metadata.sources ? this.renderSources(metadata.sources) : ''}
            </div>
        `;

        this.chatMessagesEl.appendChild(messageEl);
        this.scrollToBottom();

        return messageId;
    }

    removeMessage(messageId) {
        const el = document.getElementById(messageId);
        if (el) el.remove();
    }

    renderMessages() {
        if (this.messages.length === 0) {
            this.chatMessagesEl.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">💬</div>
                    <div class="empty-state-title">Start a Conversation</div>
                    <div class="empty-state-text">Ask me anything about your documents</div>
                </div>
            `;
            return;
        }

        this.chatMessagesEl.innerHTML = '';
        this.messages.forEach(msg => {
            this.addMessage(msg.role, msg.content, false, msg.metadata);
        });
    }

    clearChat() {
        this.messages = [];
        this.renderMessages();
        this.reasoningTraceEl.innerHTML = '<p style="color: #95a5a6; font-size: 12px;">No active query</p>';
        this.clearQueryStats();
    }

    formatMessage(content) {
        // Simple markdown formatting
        let formatted = this.escapeHtml(content);
        
        // Bold
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Code blocks
        formatted = formatted.replace(/`(.*?)`/g, '<code>$1</code>');
        
        // Line breaks
        formatted = formatted.replace(/\n/g, '<br>');
        
        return formatted;
    }

    renderSources(sources) {
        if (!sources || sources.length === 0) return '';
        
        return `
            <div class="message-sources">
                <div class="sources-header">📚 Sources:</div>
                ${sources.map((src, idx) => `
                    <div class="source-item">
                        <span class="source-number">[${idx + 1}]</span>
                        <span class="source-text">${this.escapeHtml(src.document_name || 'Unknown')}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    async updateSessionTitle(firstQuery) {
        try {
            // Use first 50 chars of query as title
            const title = firstQuery.substring(0, 50) + (firstQuery.length > 50 ? '...' : '');
            
            await fetch(`/query/sessions/${this.currentSessionId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title })
            });
            
            await this.loadSessions();
        } catch (error) {
            console.error('Failed to update session title:', error);
        }
    }

    // ==================== DEBUG TOOLS ====================

    async refreshStatus() {
        await Promise.all([
            this.refreshAgentStatus(),
            this.refreshDatabaseStatus()
        ]);
    }

    async refreshAgentStatus() {
        try {
            const response = await fetch('/agent/status');
            const data = await response.json();
            this.agentStatus = data;
            this.renderAgentStatus(data);
        } catch (error) {
            console.error('Failed to refresh agent status:', error);
        }
    }

    async refreshDatabaseStatus() {
        try {
            const response = await fetch('/database/status');
            const data = await response.json();
            this.dbStatus = data;
            this.renderDatabaseStatus(data);
        } catch (error) {
            console.error('Failed to refresh database status:', error);
        }
    }

    renderAgentStatus(data) {
        const section = document.querySelector('.debug-section:nth-child(1)');
        if (!section) return;

        section.innerHTML = `
            <h3>Agent Status</h3>
            <div class="debug-item">
                <span class="debug-label">Status:</span>
                <span class="status-badge ${data.healthy ? 'status-online' : 'status-offline'}">
                    ${data.healthy ? 'Online' : 'Offline'}
                </span>
            </div>
            <div class="debug-item">
                <span class="debug-label">LLM Model:</span>
                <span class="debug-value">${data.llm_model || 'N/A'}</span>
            </div>
            <div class="debug-item">
                <span class="debug-label">Embeddings:</span>
                <span class="debug-value">${data.embedding_model || 'N/A'}</span>
            </div>
            <div class="debug-item">
                <span class="debug-label">Max Iterations:</span>
                <span class="debug-value">${data.max_iterations || 'N/A'}</span>
            </div>
        `;
    }

    renderDatabaseStatus(data) {
        const section = document.querySelector('.debug-section:nth-child(2)');
        if (!section) return;

        const stats = data.statistics || {};
        const docStats = stats.document_status || {};

        section.innerHTML = `
            <h3>Database Status</h3>
            <div class="debug-item">
                <span class="debug-label">Connection:</span>
                <span class="status-badge ${data.healthy ? 'status-online' : 'status-offline'}">
                    ${data.healthy ? 'Connected' : 'Disconnected'}
                </span>
            </div>
            <div class="debug-item">
                <span class="debug-label">Total Chunks:</span>
                <span class="debug-value">${stats.total_chunks || 0}</span>
            </div>
            <div class="debug-item">
                <span class="debug-label">Documents:</span>
                <span class="debug-value">${stats.total_documents || 0}</span>
            </div>
            <div class="debug-item">
                <span class="debug-label">Completed:</span>
                <span class="debug-value">${docStats.completed || 0}</span>
            </div>
            <div class="debug-item">
                <span class="debug-label">Processing:</span>
                <span class="debug-value">${docStats.processing || 0}</span>
            </div>
        `;
    }

    updateReasoningTrace(trace) {
        if (!trace || trace.length === 0) {
            this.reasoningTraceEl.innerHTML = '<p style="color: #95a5a6; font-size: 12px;">No reasoning steps</p>';
            return;
        }

        this.reasoningTraceEl.innerHTML = trace.map((step, idx) => `
            <div class="reasoning-step">
                <div class="reasoning-step-type">Step ${idx + 1}: ${this.escapeHtml(step.phase || step.type || 'Unknown')}</div>
                <div class="reasoning-step-content">${this.escapeHtml(step.content || step.description || '')}</div>
            </div>
        `).join('');
    }

    updateQueryStats(data) {
        const section = document.querySelector('.debug-section:nth-child(4)');
        if (!section) return;

        const iterations = data.iterations_used || 0;
        const retrieved = (data.sources || []).length;
        const confidence = data.confidence ? (data.confidence * 100).toFixed(1) + '%' : 'N/A';
        const duration = data.processing_time ? data.processing_time.toFixed(2) + 's' : 'N/A';

        section.querySelector('.debug-item:nth-child(1) .debug-value').textContent = iterations;
        section.querySelector('.debug-item:nth-child(2) .debug-value').textContent = retrieved;
        section.querySelector('.debug-item:nth-child(3) .debug-value').textContent = confidence;
        section.querySelector('.debug-item:nth-child(4) .debug-value').textContent = duration;
    }

    clearQueryStats() {
        const section = document.querySelector('.debug-section:nth-child(4)');
        if (!section) return;

        section.querySelectorAll('.debug-value').forEach(el => {
            el.textContent = '-';
        });
    }

    // ==================== UTILITIES ====================

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));

        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        
        return date.toLocaleDateString();
    }

    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    scrollToBottom() {
        this.chatMessagesEl.scrollTop = this.chatMessagesEl.scrollHeight;
    }

    showError(message) {
        // Use toast notification if available
        if (window.UIComponents) {
            window.UIComponents.showToast(message, 'error');
        } else {
            alert(message);
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.chatApp = new ChatApp();
});
