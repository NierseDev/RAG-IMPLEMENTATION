/**
 * State Management System for Agentic RAG Frontend
 * Lightweight, vanilla JS state management with pub/sub pattern
 * Features: localStorage persistence, middleware, event-driven updates
 */

class StateManager {
    constructor(config = {}) {
        // Default state trees
        this.state = {
            chat: {
                messages: [],
                currentSession: null,
                sessionList: [],
                loadingQuery: false
            },
            document: {
                uploadedDocs: [],
                uploadProgress: {},
                selectedDoc: null,
                loadingDocs: false
            },
            debug: {
                systemStatus: {
                    agentHealthy: null,
                    dbHealthy: null,
                    llmModel: null,
                    embeddingModel: null
                },
                debugOpen: false,
                traceData: [],
                agentStatus: null
            },
            ui: {
                activeTab: 'chat',
                sidebarOpen: true,
                notifications: []
            }
        };

        this.config = {
            persistenceEnabled: true,
            persistenceKey: 'rag-app-state',
            statusUpdateInterval: 5000,
            ...config
        };

        this.subscribers = new Map();
        this.middleware = [];
        this.statusUpdateTimer = null;

        this.init();
    }

    /**
     * Initialize state manager
     */
    init() {
        if (this.config.persistenceEnabled) {
            this.hydrate();
        }
        this.startStatusUpdates();
    }

    /**
     * Get entire state or a specific branch
     * @param {string} path - Dot notation path (e.g., 'chat.messages')
     * @returns {*} State value
     */
    getState(path = null) {
        if (!path) return JSON.parse(JSON.stringify(this.state));

        const keys = path.split('.');
        let current = this.state;

        for (const key of keys) {
            if (current && typeof current === 'object' && key in current) {
                current = current[key];
            } else {
                return undefined;
            }
        }

        return JSON.parse(JSON.stringify(current));
    }

    /**
     * Set state with deep merge
     * @param {string|Object} path - Dot notation path or object to merge
     * @param {*} value - Value to set (if path is string)
     */
    setState(path, value = undefined) {
        const updates = typeof path === 'string' ? { [path]: value } : path;

        for (const [key, val] of Object.entries(updates)) {
            const keys = key.split('.');
            let current = this.state;

            // Navigate to parent
            for (let i = 0; i < keys.length - 1; i++) {
                const k = keys[i];
                if (!(k in current) || typeof current[k] !== 'object') {
                    current[k] = {};
                }
                current = current[k];
            }

            // Set value
            const lastKey = keys[keys.length - 1];
            if (typeof val === 'object' && val !== null && typeof current[lastKey] === 'object') {
                current[lastKey] = { ...current[lastKey], ...val };
            } else {
                current[lastKey] = val;
            }
        }

        // Run middleware
        this.runMiddleware(updates);

        // Notify subscribers
        this.notifySubscribers(updates);

        // Persist state
        if (this.config.persistenceEnabled) {
            this.persist();
        }
    }

    /**
     * Subscribe to state changes
     * @param {Function} listener - Callback function
     * @param {string|Array} deps - Dependencies (paths to watch)
     * @returns {Function} Unsubscribe function
     */
    subscribe(listener, deps = null) {
        const id = Math.random().toString(36).substring(7);
        
        if (!this.subscribers.has(listener)) {
            this.subscribers.set(listener, new Map());
        }

        this.subscribers.get(listener).set(id, deps);

        return () => {
            const depMap = this.subscribers.get(listener);
            if (depMap) {
                depMap.delete(id);
                if (depMap.size === 0) {
                    this.subscribers.delete(listener);
                }
            }
        };
    }

    /**
     * Unsubscribe from state changes
     * @param {Function} listener - Listener to remove
     */
    unsubscribe(listener) {
        this.subscribers.delete(listener);
    }

    /**
     * Notify all subscribers
     * @param {Object} updates - Updated state paths
     */
    notifySubscribers(updates) {
        for (const [listener, depMap] of this.subscribers.entries()) {
            for (const [, deps] of depMap) {
                // If no dependencies, notify
                if (!deps) {
                    listener(this.getState());
                    break;
                }

                // Check if any dependency was updated
                const depsArray = Array.isArray(deps) ? deps : [deps];
                const shouldNotify = depsArray.some(dep => {
                    for (const key of Object.keys(updates)) {
                        if (key.startsWith(dep) || dep.startsWith(key)) {
                            return true;
                        }
                    }
                    return false;
                });

                if (shouldNotify) {
                    listener(this.getState());
                    break;
                }
            }
        }
    }

    /**
     * Dispatch an action
     * @param {string} actionName - Name of the action
     * @param {*} payload - Action payload
     */
    async dispatch(actionName, payload = null) {
        const action = this.actions[actionName];
        
        if (!action) {
            console.warn(`Action "${actionName}" not defined`);
            return;
        }

        await action.call(this, payload);
    }

    /**
     * Add middleware
     * @param {Function} fn - Middleware function
     */
    use(fn) {
        this.middleware.push(fn);
    }

    /**
     * Run all middleware
     * @param {Object} updates - State updates
     */
    runMiddleware(updates) {
        for (const fn of this.middleware) {
            fn(updates, this.getState());
        }
    }

    /**
     * Persist state to localStorage
     */
    persist() {
        try {
            const toStore = {
                chat: {
                    sessionList: this.state.chat.sessionList,
                    currentSession: this.state.chat.currentSession
                },
                ui: this.state.ui
            };
            localStorage.setItem(this.config.persistenceKey, JSON.stringify(toStore));
        } catch (error) {
            console.error('Failed to persist state:', error);
        }
    }

    /**
     * Hydrate state from localStorage
     */
    hydrate() {
        try {
            const stored = localStorage.getItem(this.config.persistenceKey);
            if (stored) {
                const data = JSON.parse(stored);
                this.setState(data);
            }
        } catch (error) {
            console.error('Failed to hydrate state:', error);
        }
    }

    /**
     * Reset state to initial values
     */
    reset() {
        this.state = {
            chat: {
                messages: [],
                currentSession: null,
                sessionList: [],
                loadingQuery: false
            },
            document: {
                uploadedDocs: [],
                uploadProgress: {},
                selectedDoc: null,
                loadingDocs: false
            },
            debug: {
                systemStatus: {
                    agentHealthy: null,
                    dbHealthy: null,
                    llmModel: null,
                    embeddingModel: null
                },
                debugOpen: false,
                traceData: [],
                agentStatus: null
            },
            ui: {
                activeTab: 'chat',
                sidebarOpen: true,
                notifications: []
            }
        };

        localStorage.removeItem(this.config.persistenceKey);
        this.notifySubscribers({});
    }

    /**
     * Start periodic status updates
     */
    startStatusUpdates() {
        this.statusUpdateTimer = setInterval(async () => {
            await this.dispatch('refreshSystemStatus');
        }, this.config.statusUpdateInterval);
    }

    /**
     * Stop status updates
     */
    stopStatusUpdates() {
        if (this.statusUpdateTimer) {
            clearInterval(this.statusUpdateTimer);
        }
    }

    /**
     * Built-in actions
     */
    actions = {
        // ========== CHAT ACTIONS ==========
        
        addMessage: async function(message) {
            const messages = this.getState('chat.messages') || [];
            messages.push(message);
            this.setState('chat.messages', messages);
        },

        clearMessages: async function() {
            this.setState('chat.messages', []);
        },

        setCurrentSession: async function(sessionId) {
            this.setState('chat.currentSession', sessionId);
        },

        setSessionList: async function(sessions) {
            this.setState('chat.sessionList', sessions);
        },

        setLoadingQuery: async function(loading) {
            this.setState('chat.loadingQuery', loading);
        },

        loadSessions: async function() {
            try {
                this.setState('chat.loadingQuery', true);
                const response = await fetch('/query/sessions');
                const data = await response.json();
                this.setState('chat.sessionList', data.sessions || []);
            } catch (error) {
                console.error('Failed to load sessions:', error);
            } finally {
                this.setState('chat.loadingQuery', false);
            }
        },

        createSession: async function(title = 'New Chat') {
            try {
                this.setState('chat.loadingQuery', true);
                const response = await fetch('/query/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title })
                });
                const data = await response.json();
                this.setState('chat.currentSession', data.session_id);
                await this.dispatch('loadSessions');
                return data.session_id;
            } catch (error) {
                console.error('Failed to create session:', error);
                throw error;
            } finally {
                this.setState('chat.loadingQuery', false);
            }
        },

        sendQuery: async function(payload) {
            const { query, sessionId } = payload;
            
            try {
                this.setState('chat.loadingQuery', true);

                const response = await fetch('/query/agentic', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        session_id: sessionId
                    })
                });

                const data = await response.json();
                
                this.setState({
                    'chat.messages': [...(this.getState('chat.messages') || []), {
                        role: 'user',
                        content: query,
                        timestamp: new Date().toISOString()
                    }, {
                        role: 'assistant',
                        content: data.answer,
                        timestamp: new Date().toISOString(),
                        metadata: data
                    }],
                    'debug.traceData': data.reasoning_trace || []
                });

                return data;
            } catch (error) {
                console.error('Failed to send query:', error);
                throw error;
            } finally {
                this.setState('chat.loadingQuery', false);
            }
        },

        // ========== DOCUMENT ACTIONS ==========

        loadDocuments: async function() {
            try {
                this.setState('document.loadingDocs', true);
                const response = await fetch('/ingest/documents?page=1&page_size=100');
                const data = await response.json();
                this.setState('document.uploadedDocs', data.documents || []);
            } catch (error) {
                console.error('Failed to load documents:', error);
            } finally {
                this.setState('document.loadingDocs', false);
            }
        },

        addDocument: async function(document) {
            const docs = this.getState('document.uploadedDocs') || [];
            docs.push(document);
            this.setState('document.uploadedDocs', docs);
        },

        updateDocumentProgress: async function(payload) {
            const { docId, progress } = payload;
            const current = this.getState('document.uploadProgress') || {};
            current[docId] = progress;
            this.setState('document.uploadProgress', current);
        },

        removeDocument: async function(docId) {
            try {
                await fetch(`/ingest/documents/${docId}`, { method: 'DELETE' });
                const docs = this.getState('document.uploadedDocs') || [];
                this.setState('document.uploadedDocs', 
                    docs.filter(d => d.id !== docId)
                );
            } catch (error) {
                console.error('Failed to delete document:', error);
                throw error;
            }
        },

        selectDocument: async function(docId) {
            this.setState('document.selectedDoc', docId);
        },

        // ========== DEBUG ACTIONS ==========

        refreshSystemStatus: async function() {
            try {
                const [agentRes, dbRes] = await Promise.all([
                    fetch('/agent/status'),
                    fetch('/database/status')
                ]);

                const agentData = await agentRes.json();
                const dbData = await dbRes.json();

                this.setState({
                    'debug.systemStatus': {
                        agentHealthy: agentData.healthy,
                        dbHealthy: dbData.healthy,
                        llmModel: agentData.llm_model,
                        embeddingModel: agentData.embedding_model
                    },
                    'debug.agentStatus': agentData
                });
            } catch (error) {
                console.error('Failed to refresh system status:', error);
            }
        },

        setDebugOpen: async function(open) {
            this.setState('debug.debugOpen', open);
        },

        setTraceData: async function(traceData) {
            this.setState('debug.traceData', traceData);
        },

        // ========== UI ACTIONS ==========

        setActiveTab: async function(tabName) {
            this.setState('ui.activeTab', tabName);
        },

        toggleSidebar: async function() {
            const current = this.getState('ui.sidebarOpen');
            this.setState('ui.sidebarOpen', !current);
        },

        setSidebarOpen: async function(open) {
            this.setState('ui.sidebarOpen', open);
        },

        addNotification: async function(payload) {
            const { message, type = 'info', duration = 3000, id } = payload;
            const notifications = this.getState('ui.notifications') || [];
            const notifId = id || Math.random().toString(36).substring(7);

            notifications.push({
                id: notifId,
                message,
                type,
                timestamp: new Date().toISOString()
            });

            this.setState('ui.notifications', notifications);

            // Auto-remove after duration
            if (duration > 0) {
                setTimeout(() => {
                    this.dispatch('removeNotification', notifId);
                }, duration);
            }

            return notifId;
        },

        removeNotification: async function(notifId) {
            const notifications = this.getState('ui.notifications') || [];
            this.setState('ui.notifications',
                notifications.filter(n => n.id !== notifId)
            );
        },

        clearNotifications: async function() {
            this.setState('ui.notifications', []);
        }
    };

    /**
     * Destroy state manager and cleanup
     */
    destroy() {
        this.stopStatusUpdates();
        this.subscribers.clear();
        this.middleware = [];
    }
}

/**
 * Hook-like utilities for components
 */
const StateHooks = {
    /**
     * useState-like hook for reading state
     * @param {string} path - State path to watch
     * @param {Function} callback - Callback when state changes
     * @returns {Function} Unsubscribe function
     */
    useState(path, callback) {
        if (!window.StateManagerInstance) {
            console.warn('StateManager not initialized');
            return () => {};
        }

        const unsubscribe = window.StateManagerInstance.subscribe(
            (state) => {
                const value = window.StateManagerInstance.getState(path);
                callback(value);
            },
            [path]
        );

        // Call immediately with current value
        const value = window.StateManagerInstance.getState(path);
        callback(value);

        return unsubscribe;
    },

    /**
     * useDispatch-like hook for dispatching actions
     * @param {string} actionName - Action name
     * @returns {Function} Dispatch function
     */
    useDispatch(actionName) {
        if (!window.StateManagerInstance) {
            console.warn('StateManager not initialized');
            return async () => {};
        }

        return async (payload) => {
            return window.StateManagerInstance.dispatch(actionName, payload);
        };
    },

    /**
     * useSelector-like hook for selecting state
     * @param {Function|string} selector - Selector function or state path
     * @param {Function} callback - Callback when selected state changes
     * @returns {Function} Unsubscribe function
     */
    useSelector(selector, callback) {
        if (!window.StateManagerInstance) {
            console.warn('StateManager not initialized');
            return () => {};
        }

        const unsubscribe = window.StateManagerInstance.subscribe(
            (state) => {
                const value = typeof selector === 'function'
                    ? selector(state)
                    : window.StateManagerInstance.getState(selector);
                callback(value);
            }
        );

        // Call immediately
        const value = typeof selector === 'function'
            ? selector(window.StateManagerInstance.getState())
            : window.StateManagerInstance.getState(selector);
        callback(value);

        return unsubscribe;
    },

    /**
     * useEffect-like hook for listening to state changes with dependencies
     * @param {Function} listener - Listener callback
     * @param {Array} deps - Dependencies to watch
     * @returns {Function} Unsubscribe function
     */
    useEffect(listener, deps = []) {
        if (!window.StateManagerInstance) {
            console.warn('StateManager not initialized');
            return () => {};
        }

        const unsubscribe = window.StateManagerInstance.subscribe(listener, deps);

        // Call immediately
        listener(window.StateManagerInstance.getState());

        return unsubscribe;
    }
};

/**
 * Initialize global state manager instance
 */
function initStateManager(config = {}) {
    if (window.StateManagerInstance) {
        console.warn('StateManager already initialized');
        return window.StateManagerInstance;
    }

    window.StateManagerInstance = new StateManager(config);

    // Add localStorage persistence middleware
    window.StateManagerInstance.use((updates) => {
        // Middleware can be used for logging, analytics, etc.
    });

    return window.StateManagerInstance;
}

// Export for both ES6 and global scope
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { StateManager, StateHooks, initStateManager };
}
