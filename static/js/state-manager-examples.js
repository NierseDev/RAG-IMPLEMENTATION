/**
 * State Manager Integration Examples
 * Demonstrates how to use the state management system with existing components
 */

// ========== EXAMPLE 1: Using useState Hook ==========

// Listen to chat messages
StateHooks.useState('chat.messages', (messages) => {
    console.log('Messages updated:', messages);
    // Update UI with new messages
});

// Listen to loading state
StateHooks.useState('chat.loadingQuery', (loading) => {
    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) {
        sendBtn.disabled = loading;
    }
});

// ========== EXAMPLE 2: Using useDispatch Hook ==========

const sendMessage = async (text) => {
    const dispatch = StateHooks.useDispatch('sendQuery');
    const sessionId = StateHooks.useSelector('chat.currentSession', (val) => val);
    
    try {
        await dispatch({
            query: text,
            sessionId: sessionId
        });
    } catch (error) {
        console.error('Failed to send message:', error);
    }
};

// ========== EXAMPLE 3: Using useSelector Hook ==========

// Select and react to specific state
StateHooks.useSelector(
    (state) => state.chat.sessionList,
    (sessionList) => {
        console.log('Session list updated:', sessionList);
        // Render sessions list
    }
);

// ========== EXAMPLE 4: Using useEffect Hook ==========

// React to multiple state changes
StateHooks.useEffect(
    (state) => {
        const docs = state.document.uploadedDocs;
        const loading = state.document.loadingDocs;
        console.log('Documents:', docs, 'Loading:', loading);
    },
    ['document.uploadedDocs', 'document.loadingDocs']
);

// ========== EXAMPLE 5: Integrating ChatApp with State Manager ==========

class ChatAppWithStateManager extends ChatApp {
    constructor() {
        super();
        this.setupStateListeners();
    }

    setupStateListeners() {
        // Listen to chat messages
        this.unsubscribeChatMessages = StateHooks.useState('chat.messages', (messages) => {
            this.messages = messages || [];
            this.renderMessages();
        });

        // Listen to session list
        this.unsubscribeSessions = StateHooks.useState('chat.sessionList', (sessions) => {
            this.sessions = sessions || [];
            this.renderSessions();
        });

        // Listen to current session
        this.unsubscribeSession = StateHooks.useState('chat.currentSession', (sessionId) => {
            this.currentSessionId = sessionId;
        });

        // Listen to loading state
        this.unsubscribeLoading = StateHooks.useState('chat.loadingQuery', (loading) => {
            this.isProcessing = loading;
            this.sendBtn.disabled = loading;
        });
    }

    async sendMessage() {
        const query = this.chatInputEl.value.trim();
        if (!query || this.isProcessing) return;

        // Create session if needed
        if (!this.currentSessionId) {
            const dispatch = StateHooks.useDispatch('createSession');
            this.currentSessionId = await dispatch('New Chat');
        }

        this.chatInputEl.value = '';
        this.chatInputEl.style.height = 'auto';

        // Add user message
        await StateHooks.useDispatch('addMessage')({
            role: 'user',
            content: query,
            timestamp: new Date().toISOString()
        });

        // Send query
        const dispatch = StateHooks.useDispatch('sendQuery');
        try {
            await dispatch({
                query: query,
                sessionId: this.currentSessionId
            });
        } catch (error) {
            console.error('Failed to send query:', error);
        }
    }

    cleanup() {
        this.unsubscribeChatMessages();
        this.unsubscribeSessions();
        this.unsubscribeSession();
        this.unsubscribeLoading();
        super.cleanup?.();
    }
}

// ========== EXAMPLE 6: Integrating IngestApp with State Manager ==========

class IngestAppWithStateManager extends IngestApp {
    constructor() {
        super();
        this.setupStateListeners();
    }

    setupStateListeners() {
        // Listen to uploaded documents
        this.unsubscribeDocs = StateHooks.useState('document.uploadedDocs', (docs) => {
            this.documents = docs || [];
            this.renderDocuments();
        });

        // Listen to loading state
        this.unsubscribeLoading = StateHooks.useState('document.loadingDocs', (loading) => {
            // Update UI to show loading state
        });

        // Listen to upload progress
        this.unsubscribeProgress = StateHooks.useState('document.uploadProgress', (progress) => {
            Object.entries(progress || {}).forEach(([docId, pct]) => {
                const el = document.querySelector(`[data-doc-id="${docId}"] .progress-bar`);
                if (el) el.style.width = pct + '%';
            });
        });
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
                // Add to state
                const dispatch = StateHooks.useDispatch('addDocument');
                await dispatch(data);

                // Reload documents from API
                await StateHooks.useDispatch('loadDocuments')();
            } else {
                console.error(`Upload failed: ${data.detail}`);
            }
        } finally {
            this.hideUploadProgress();
        }
    }

    cleanup() {
        this.unsubscribeDocs();
        this.unsubscribeLoading();
        this.unsubscribeProgress();
        super.cleanup?.();
    }
}

// ========== EXAMPLE 7: Global Notification System ==========

class NotificationManager {
    static showSuccess(message, duration = 3000) {
        StateHooks.useDispatch('addNotification')({
            message,
            type: 'success',
            duration
        });
    }

    static showError(message, duration = 3000) {
        StateHooks.useDispatch('addNotification')({
            message,
            type: 'error',
            duration
        });
    }

    static showInfo(message, duration = 3000) {
        StateHooks.useDispatch('addNotification')({
            message,
            type: 'info',
            duration
        });
    }

    static showWarning(message, duration = 3000) {
        StateHooks.useDispatch('addNotification')({
            message,
            type: 'warning',
            duration
        });
    }
}

// Usage:
// NotificationManager.showSuccess('Document uploaded!');
// NotificationManager.showError('Failed to load sessions');

// ========== EXAMPLE 8: State Persistence ==========

// State is automatically persisted to localStorage when you call setState
// To manually persist:
// window.StateManagerInstance.persist();

// To load from localStorage:
// window.StateManagerInstance.hydrate();

// To clear all state:
// window.StateManagerInstance.reset();

// ========== EXAMPLE 9: Middleware for Logging ==========

// Add logging middleware
window.StateManagerInstance.use((updates, newState) => {
    console.log('State updated:', updates);
    console.log('New state:', newState);
});

// ========== EXAMPLE 10: Debug State Inspector ==========

class StateDebugger {
    static inspect(path = null) {
        const state = window.StateManagerInstance.getState(path);
        console.table(state);
        return state;
    }

    static watch(path) {
        console.log(`Watching: ${path}`);
        return StateHooks.useState(path, (value) => {
            console.log(`${path} changed:`, value);
        });
    }

    static getStats() {
        return {
            subscribers: window.StateManagerInstance.subscribers.size,
            middleware: window.StateManagerInstance.middleware.length,
            state: window.StateManagerInstance.getState()
        };
    }
}

// Usage in console:
// StateDebugger.inspect('chat');
// StateDebugger.watch('document.uploadedDocs');
// StateDebugger.getStats();
