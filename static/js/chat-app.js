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
        
        // Auto-refresh status every minute
        setInterval(() => this.refreshStatus(), 60000);
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
        this.agentStatusValueEl = document.getElementById('agentStatusValue');
        this.agentModelValueEl = document.getElementById('agentModelValue');
        this.agentEmbeddingsValueEl = document.getElementById('agentEmbeddingsValue');
        this.databaseConnectionValueEl = document.getElementById('databaseConnectionValue');
        this.databaseChunksValueEl = document.getElementById('databaseChunksValue');
        this.databaseDocumentsValueEl = document.getElementById('databaseDocumentsValue');
        this.queryIterationsValueEl = document.getElementById('queryIterationsValue');
        this.queryRetrievedValueEl = document.getElementById('queryRetrievedValue');
        this.queryConfidenceValueEl = document.getElementById('queryConfidenceValue');
        this.queryDurationValueEl = document.getElementById('queryDurationValue');
        this.reasoningTraceValueEl = document.getElementById('reasoningTraceValue');
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
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
            const data = await response.json();

            this.sessions = (data.sessions || []).map(session => this.normalizeSession(session));
            this.renderSessions();
            
            // Load most recent session if available
            if (this.sessions.length > 0 && !this.currentSessionId) {
                await this.loadSession(this.sessions[0].id);
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
            <div class="chat-item ${session.id === this.currentSessionId ? 'active' : ''}" 
                 data-session-id="${session.id}">
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
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
            const data = await response.json();
            const sessionId = this.extractSessionId(data.session || data);
            if (!sessionId) {
                throw new Error('Session ID missing from create session response');
            }
            this.currentSessionId = sessionId;
            
            await this.loadSessions();
            this.clearChat();
            this.chatInputEl.focus();
            return true;
        } catch (error) {
            console.error('Failed to create session:', error);
            this.showError('Failed to create new chat');
            return false;
        }
    }

    async loadSession(sessionId) {
        try {
            const response = await fetch(`/query/sessions/${sessionId}`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
            const data = await response.json();
            
            this.currentSessionId = Number(sessionId);
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
            const response = await fetch(`/query/sessions/${sessionId}`, { method: 'DELETE' });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
            
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
            const created = await this.createNewSession();
            if (!created || !this.currentSessionId) {
                this.showError('Unable to initialize chat session');
                return;
            }
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
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.detail || `Request failed with status ${response.status}`);
            }
            if (!data.answer) {
                throw new Error('Empty response from agentic endpoint');
            }

            // Remove loading message
            this.removeMessage(loadingId);
            await this.renderSuccessfulResponse(data, query);

        } catch (error) {
            console.error('Failed to send message:', error);
            this.removeMessage(loadingId);
            const errorMessage = error?.message || 'Unknown error';
            this.addMessage('assistant', `❌ Failed to process query: ${errorMessage}`);
            this.showError(`Failed to send message: ${errorMessage}`);
        } finally {
            this.isProcessing = false;
            this.sendBtn.disabled = false;
            this.chatInputEl.focus();
        }
    }

    async renderSuccessfulResponse(data, query) {
        try {
            // Add assistant response first so the answer survives even if debug UI fails.
            this.addMessage('assistant', data.answer, false, data);
        } catch (error) {
            console.error('Failed to render assistant response:', error);
            this.addMessage('assistant', data.answer);
        }

        try {
            this.updateReasoningTrace(data.reasoning_trace);
        } catch (error) {
            console.warn('Failed to update reasoning trace:', error);
        }

        try {
            this.updateQueryStats(data);
        } catch (error) {
            console.warn('Failed to update query stats:', error);
        }

        try {
            if (this.messages.length === 2) { // user + assistant
                await this.updateSessionTitle(query);
            }
        } catch (error) {
            console.warn('Failed to update session title:', error);
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
        this.setText(this.reasoningTraceValueEl, 'No active query');
        if (this.reasoningTraceEl) {
            this.reasoningTraceEl.innerHTML = '<p style="color: #95a5a6; font-size: 12px;">No active query</p>';
        }
        this.clearQueryStats();
    }

    formatMessage(content) {
        // Simple markdown formatting
        let formatted = this.escapeHtml(content ?? '');
        
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
                        <span class="source-text">
                            ${this.escapeHtml(
                                typeof src === 'string'
                                    ? src
                                    : (src.document_name || src.title || src.filename || src.source || src.chunk_id || 'Unknown')
                            )}
                        </span>
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
        const isOnline = data?.status === 'online' || data?.status === 'healthy' || data?.healthy === true;
        const llmModel = data?.llm?.model || data?.llm_model || 'N/A';
        const embeddingModel = data?.embeddings?.model || data?.embedding_model || 'N/A';
        this.setStatusValue(this.agentStatusValueEl, isOnline ? 'Online' : 'Offline', isOnline);
        this.setText(this.agentModelValueEl, llmModel);
        this.setText(this.agentEmbeddingsValueEl, embeddingModel);
    }

    renderDatabaseStatus(data) {
        const stats = data?.statistics || {};
        const docStats = stats.document_status || {};
        const connected = data?.status === 'connected' || data?.healthy === true;
        const totalChunks = data?.chunks?.total ?? stats.total_chunks ?? 0;
        const totalDocuments = data?.documents?.total ?? stats.total_documents ?? 0;

        this.setStatusValue(this.databaseConnectionValueEl, connected ? 'Connected' : 'Disconnected', connected);
        this.setText(this.databaseChunksValueEl, totalChunks);
        this.setText(this.databaseDocumentsValueEl, totalDocuments);
    }

    updateReasoningTrace(trace) {
        if (!this.reasoningTraceEl) return;
        if (!trace || trace.length === 0) {
            this.setText(this.reasoningTraceValueEl, 'No reasoning steps');
            this.reasoningTraceEl.innerHTML = '<p style="color: #95a5a6; font-size: 12px;">No reasoning steps</p>';
            return;
        }

        this.setText(this.reasoningTraceValueEl, `${trace.length} step${trace.length === 1 ? '' : 's'}`);
        this.reasoningTraceEl.innerHTML = trace.map((step, idx) => `
            <div class="reasoning-step">
                <div class="reasoning-step-type">Step ${idx + 1}: ${this.escapeHtml(typeof step === 'string' ? 'Reasoning' : (step.phase || step.type || 'Unknown'))}</div>
                <div class="reasoning-step-content">${this.escapeHtml(typeof step === 'string' ? step : (step.content || step.description || ''))}</div>
            </div>
        `).join('');
    }

    updateQueryStats(data) {
        const iterations = data.iterations || data.iterations_used || 0;
        const retrieved = (data.sources || []).length;
        const confidence = data.confidence ? (data.confidence * 100).toFixed(1) + '%' : 'N/A';
        const duration = data.processing_time ? data.processing_time.toFixed(2) + 's' : 'N/A';
        this.setText(this.queryIterationsValueEl, iterations);
        this.setText(this.queryRetrievedValueEl, retrieved);
        this.setText(this.queryConfidenceValueEl, confidence);
        this.setText(this.queryDurationValueEl, duration);
    }

    clearQueryStats() {
        this.setText(this.queryIterationsValueEl, '-');
        this.setText(this.queryRetrievedValueEl, '-');
        this.setText(this.queryConfidenceValueEl, '-');
        this.setText(this.queryDurationValueEl, '-');
    }

    // ==================== UTILITIES ====================

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    setText(element, value) {
        if (!element) return;
        element.textContent = value;
    }

    setStatusValue(element, value, isOnline) {
        if (!element) return;
        element.textContent = value;
        element.classList.toggle('status-online', !!isOnline);
        element.classList.toggle('status-offline', !isOnline);
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

    extractSessionId(sessionLike) {
        if (!sessionLike || typeof sessionLike !== 'object') return null;
        return Number(sessionLike.session_id ?? sessionLike.id ?? null) || null;
    }

    normalizeSession(session) {
        const id = this.extractSessionId(session);
        return { ...session, id, session_id: id };
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.chatApp = new ChatApp();
});
