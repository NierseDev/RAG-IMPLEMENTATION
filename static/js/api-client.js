/**
 * Agentic RAG API Client
 * TypeScript-like JavaScript API wrapper for the RAG backend
 * 
 * @module api-client
 * @version 1.0.0
 */

/**
 * @typedef {Object} QueryOptions
 * @property {number} [top_k=5] - Number of documents to retrieve
 * @property {string} [filter_source] - Filter results by source
 * @property {boolean} [trace=false] - Include detailed reasoning trace
 * @property {number} [timeout=30000] - Request timeout in milliseconds
 */

/**
 * @typedef {Object} IngestOptions
 * @property {string} [sourcePrefix] - Prefix to add to document source
 * @property {string} [duplicateAction='skip'] - How to handle duplicates: 'skip', 'replace', 'append'
 * @property {Function} [onProgress] - Callback for upload progress
 * @property {number} [timeout=120000] - Request timeout in milliseconds
 */

/**
 * @typedef {Object} RequestConfig
 * @property {number} [timeout=30000] - Request timeout in milliseconds
 * @property {Object} [headers] - Additional headers
 * @property {number} [retries=3] - Number of retry attempts
 * @property {number} [retryDelay=1000] - Delay between retries in milliseconds
 */

/**
 * @typedef {Object} QueryResponse
 * @property {string} query - Original query text
 * @property {string} answer - Generated answer
 * @property {number} confidence - Confidence score (0-1)
 * @property {Array<Object>} sources - Retrieved source documents
 * @property {Array<string>} reasoning_trace - Reasoning steps
 * @property {number} iterations - Number of agent iterations
 * @property {number} retrieved_chunks - Number of retrieved chunks
 * @property {boolean} verification_passed - Whether verification passed
 * @property {number} processing_time - Processing time in seconds
 * @property {Array<Object>} [retrieved_chunks_detail] - Detailed chunk information
 * @property {Array<Object>} [verification_detail] - Detailed verification information
 * @property {Array<Object>} [agent_steps] - Agent reasoning steps
 */

/**
 * @typedef {Object} IngestResponse
 * @property {boolean} success - Operation success status
 * @property {string} message - Response message
 * @property {string} source - Document source
 * @property {number} chunks_created - Number of chunks created
 * @property {number} file_size - File size in bytes
 * @property {number} processing_time - Processing time in seconds
 * @property {string} file_hash - File hash for duplicate detection
 * @property {string} duplicate_action - Action taken for duplicates
 * @property {Array<string>} validation_warnings - Validation warnings
 * @property {Object} metadata_extracted - Extracted document metadata
 */

/**
 * @typedef {Object} ChatSession
 * @property {number} id - Session ID
 * @property {string} title - Session title
 * @property {string} created_at - Creation timestamp
 * @property {string} updated_at - Last update timestamp
 */

/**
 * @typedef {Object} ChatMessage
 * @property {number} id - Message ID
 * @property {number} session_id - Associated session ID
 * @property {string} role - Message role ('user' or 'assistant')
 * @property {string} content - Message content
 * @property {string} created_at - Message timestamp
 */

/**
 * @typedef {Object} APIError
 * @property {number} status - HTTP status code
 * @property {string} message - Error message
 * @property {string} [detail] - Detailed error information
 * @property {Error} [originalError] - Original error object
 */

/**
 * APIClient - Main API client for Agentic RAG
 */
class APIClient {
  /**
   * Create an API client instance
   * @param {string} [baseURL=''] - Base URL for API endpoints
   * @param {RequestConfig} [config={}] - Configuration options
   */
  constructor(baseURL = '', config = {}) {
    this.baseURL = baseURL || this.getDefaultBaseURL();
    this.config = {
      timeout: config.timeout || 30000,
      headers: config.headers || {},
      retries: config.retries !== undefined ? config.retries : 3,
      retryDelay: config.retryDelay || 1000,
      ...config
    };
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      ...this.config.headers
    };
    this.sessionId = null;
    this.retryableStatuses = [408, 429, 500, 502, 503, 504];
  }

  /**
   * Get default base URL based on environment
   * @private
   * @returns {string} Default base URL
   */
  getDefaultBaseURL() {
    // In browser, use relative path
    if (typeof window !== 'undefined') {
      return '';
    }
    return 'http://localhost:8000';
  }

  /**
   * Set authentication token
   * @param {string} token - Authentication token
   */
  setAuthToken(token) {
    this.defaultHeaders['Authorization'] = `Bearer ${token}`;
  }

  /**
   * Remove authentication token
   */
  clearAuthToken() {
    delete this.defaultHeaders['Authorization'];
  }

  /**
   * Set current session ID
   * @param {number|string} sessionId - Session ID
   */
  setSessionId(sessionId) {
    this.sessionId = sessionId;
  }

  /**
   * Get current session ID
   * @returns {number|string|null} Current session ID
   */
  getSessionId() {
    return this.sessionId;
  }

  /**
   * Make an HTTP request with retry logic
   * @private
   * @param {string} method - HTTP method
   * @param {string} endpoint - API endpoint
   * @param {Object} [options={}] - Request options
   * @returns {Promise<Object>} Response data
   * @throws {APIError} If request fails
   */
  async request(method, endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      ...this.config,
      ...options,
      method,
      headers: {
        ...this.defaultHeaders,
        ...(options.headers || {})
      }
    };

    let lastError;
    let retries = 0;

    while (retries <= config.retries) {
      try {
        const response = await this._fetch(url, config);
        return response;
      } catch (error) {
        lastError = error;

        // Check if error is retryable
        if (
          retries < config.retries &&
          this._isRetryableError(error)
        ) {
          retries++;
          const delay = config.retryDelay * Math.pow(2, retries - 1);
          await this._sleep(delay);
          continue;
        }

        throw error;
      }
    }

    throw lastError;
  }

  /**
   * Execute fetch with timeout
   * @private
   * @param {string} url - Request URL
   * @param {Object} config - Fetch config
   * @returns {Promise<Object>} Response data
   */
  async _fetch(url, config) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), config.timeout);

    try {
      const response = await fetch(url, {
        method: config.method,
        headers: config.headers,
        body: config.body,
        signal: controller.signal,
        ...config.fetchOptions
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new APIError(
          response.status,
          data.detail || response.statusText,
          data
        );
      }

      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof APIError) {
        throw error;
      }
      throw new APIError(0, error.message, { originalError: error });
    }
  }

  /**
   * Check if error is retryable
   * @private
   * @param {Error} error - Error object
   * @returns {boolean} Whether error is retryable
   */
  _isRetryableError(error) {
    if (!(error instanceof APIError)) {
      return false;
    }
    return this.retryableStatuses.includes(error.status);
  }

  /**
   * Sleep for specified duration
   * @private
   * @param {number} ms - Milliseconds to sleep
   * @returns {Promise<void>}
   */
  _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Make a GET request
   * @private
   * @param {string} endpoint - API endpoint
   * @param {Object} [options={}] - Request options
   * @returns {Promise<Object>} Response data
   */
  async get(endpoint, options = {}) {
    return this.request('GET', endpoint, options);
  }

  /**
   * Make a POST request
   * @private
   * @param {string} endpoint - API endpoint
   * @param {Object} [body] - Request body
   * @param {Object} [options={}] - Request options
   * @returns {Promise<Object>} Response data
   */
  async post(endpoint, body, options = {}) {
    const finalOptions = {
      ...options,
      body: body ? JSON.stringify(body) : undefined
    };
    return this.request('POST', endpoint, finalOptions);
  }

  /**
   * Make a DELETE request
   * @private
   * @param {string} endpoint - API endpoint
   * @param {Object} [options={}] - Request options
   * @returns {Promise<Object>} Response data
   */
  async delete(endpoint, options = {}) {
    return this.request('DELETE', endpoint, options);
  }

  /**
   * Make a PATCH request
   * @private
   * @param {string} endpoint - API endpoint
   * @param {Object} [body] - Request body
   * @param {Object} [options={}] - Request options
   * @returns {Promise<Object>} Response data
   */
  async patch(endpoint, body, options = {}) {
    const finalOptions = {
      ...options,
      body: body ? JSON.stringify(body) : undefined
    };
    return this.request('PATCH', endpoint, finalOptions);
  }

  // ========================================================================
  // Query/Chat Endpoints
  // ========================================================================

  /**
   * Submit a query using agentic reasoning
   * @param {string} question - Question to ask
   * @param {QueryOptions} [options={}] - Query options
   * @returns {Promise<QueryResponse>} Query response with answer and traces
   * @throws {APIError} If query fails
   * 
   * @example
   * const response = await client.query('What is machine learning?', {
   *   top_k: 5,
   *   trace: true,
   *   timeout: 60000
   * });
   */
  async query(question, options = {}) {
    const body = {
      query: question,
      top_k: options.top_k || 5,
      ...(options.filter_source && { filter_source: options.filter_source })
    };

    const timeout = options.timeout || 60000;
    return this.post('/query/agentic', body, { timeout });
  }

  /**
   * Submit a simple RAG query without agentic reasoning
   * @param {string} question - Question to ask
   * @param {QueryOptions} [options={}] - Query options
   * @returns {Promise<Object>} Simple query response
   * @throws {APIError} If query fails
   * 
   * @example
   * const response = await client.querySimple('What is RAG?', { top_k: 3 });
   */
  async querySimple(question, options = {}) {
    const body = {
      query: question,
      top_k: options.top_k || 5
    };

    return this.post('/query/simple', body, {
      timeout: options.timeout || 30000
    });
  }

  /**
   * Create a new chat session
   * @param {string} [title] - Session title
   * @returns {Promise<{success: boolean, session: ChatSession}>} Created session
   * @throws {APIError} If session creation fails
   * 
   * @example
   * const result = await client.createChatSession('My Chat');
   * const sessionId = result.session.id;
   */
  async createChatSession(title) {
    const result = await this.post('/query/sessions', title ? { title } : {});
    
    if (result.success) {
      const sessionId = result.session_id || result.session?.session_id || result.session?.id;
      if (sessionId) this.setSessionId(sessionId);
    }
    
    return result;
  }

  /**
   * List all chat sessions
   * @param {number} [limit=50] - Maximum number of sessions to return
   * @param {number} [offset=0] - Offset for pagination
   * @returns {Promise<{success: boolean, sessions: ChatSession[], count: number}>} List of sessions
   * @throws {APIError} If listing fails
   */
  async listChatSessions(limit = 50, offset = 0) {
    return this.get(`/query/sessions?limit=${limit}&offset=${offset}`);
  }

  /**
   * Get a specific chat session with its messages
   * @param {number} sessionId - Session ID
   * @returns {Promise<{success: boolean, session: ChatSession, messages: ChatMessage[]}>} Session and messages
   * @throws {APIError} If session not found or request fails
   * 
   * @example
   * const result = await client.getChatSession(123);
   * console.log(result.messages); // All messages in session
   */
  async getChatSession(sessionId) {
    return this.get(`/query/sessions/${sessionId}`);
  }

  /**
   * Get chat history for a session
   * @param {number} [sessionId] - Session ID (uses current session if not provided)
   * @returns {Promise<Object>} Chat history and metadata
   * @throws {APIError} If session not found or request fails
   */
  async getChatHistory(sessionId) {
    const id = sessionId || this.sessionId;
    if (!id) {
      throw new APIError(400, 'Session ID required. Set with setSessionId() or provide as parameter.');
    }
    return this.getChatSession(id);
  }

  /**
   * Delete a chat session
   * @param {number} sessionId - Session ID to delete
   * @returns {Promise<{success: boolean, message: string}>} Deletion result
   * @throws {APIError} If deletion fails
   */
  async deleteChatSession(sessionId) {
    return this.delete(`/query/sessions/${sessionId}`);
  }

  // ========================================================================
  // Document Ingestion Endpoints
  // ========================================================================

  /**
   * Ingest a single document
   * @param {File|Blob} file - File to ingest
   * @param {IngestOptions} [options={}] - Ingestion options
   * @returns {Promise<IngestResponse>} Ingestion result
   * @throws {APIError} If ingestion fails
   * 
   * @example
   * const file = document.querySelector('input[type="file"]').files[0];
   * const result = await client.ingest(file, {
   *   sourcePrefix: 'documents',
   *   onProgress: (percent) => console.log(`${percent}% uploaded`)
   * });
   */
  async ingest(file, options = {}) {
    const formData = new FormData();
    formData.append('file', file);

    if (options.sourcePrefix) {
      formData.append('source', `${options.sourcePrefix}/${file.name}`);
    }

    return this.request('POST', '/ingest', {
      body: formData,
      headers: {}, // Let browser set Content-Type with boundary
      timeout: options.timeout || 120000,
      fetchOptions: options.onProgress
        ? this._createProgressFetchOptions(options.onProgress)
        : {}
    });
  }

  /**
   * Ingest multiple documents
   * @param {File[]|Blob[]} files - Files to ingest
   * @param {IngestOptions} [options={}] - Ingestion options
   * @returns {Promise<Object>} Batch ingestion result
   * @throws {APIError} If ingestion fails
   * 
   * @example
   * const files = document.querySelector('input[type="file"]').files;
   * const result = await client.ingestBatch(files, {
   *   sourcePrefix: 'documents',
   *   duplicateAction: 'replace',
   *   onProgress: (percent) => updateProgressBar(percent)
   * });
   */
  async ingestBatch(files, options = {}) {
    const formData = new FormData();

    Array.from(files).forEach(file => {
      formData.append('files', file);
    });

    if (options.sourcePrefix) {
      formData.append('source_prefix', options.sourcePrefix);
    }

    formData.append(
      'duplicate_action',
      options.duplicateAction || 'skip'
    );

    return this.request('POST', '/ingest/batch', {
      body: formData,
      headers: {},
      timeout: options.timeout || 300000,
      fetchOptions: options.onProgress
        ? this._createProgressFetchOptions(options.onProgress)
        : {}
    });
  }

  /**
   * Check which files already exist in the knowledge base
   * @param {string[]} filenames - Filenames to check
   * @param {string} [sourcePrefix] - Optional prefix to prepend to filenames
   * @returns {Promise<Object>} Existence check results
   * @throws {APIError} If check fails
   * 
   * @example
   * const result = await client.checkDuplicates(
   *   ['document1.pdf', 'document2.pdf'],
   *   'documents'
   * );
   * console.log(result.results); // { 'document1.pdf': { exists: true, ... }, ... }
   */
  async checkDuplicates(filenames, sourcePrefix) {
    const body = {
      filenames,
      ...(sourcePrefix && { source_prefix: sourcePrefix })
    };

    return this.post('/ingest/check-duplicates', body);
  }

  /**
   * Get list of all documents in the knowledge base
   * @returns {Promise<{documents: Array, total: number}>} Document list
   * @throws {APIError} If retrieval fails
   * 
   * @example
   * const result = await client.getDocuments();
   * console.log(result.documents); // List of document sources
   */
  async getDocuments() {
    return this.get('/ingest/documents');
  }

  /**
   * Get detailed information about a specific document
   * @param {number} documentId - Document ID
   * @returns {Promise<Object>} Document details and metadata
   * @throws {APIError} If document not found
   */
  async getDocumentDetails(documentId) {
    return this.get(`/ingest/documents/${documentId}`);
  }

  /**
   * Get all chunks for a specific document
   * @param {number} documentId - Document ID
   * @param {number} [limit=50] - Maximum chunks to return
   * @param {number} [offset=0] - Offset for pagination
   * @returns {Promise<{success: boolean, chunks: Array, total: number}>} Document chunks
   * @throws {APIError} If document not found
   */
  async getDocumentChunks(documentId, limit = 50, offset = 0) {
    return this.get(
      `/ingest/documents/${documentId}/chunks?limit=${limit}&offset=${offset}`
    );
  }

  /**
   * Delete a document by source name
   * @param {string} source - Document source name
   * @returns {Promise<{success: boolean, message: string, deleted_chunks: number}>} Deletion result
   * @throws {APIError} If deletion fails
   * 
   * @example
   * const result = await client.deleteDocument('documents/report.pdf');
   * console.log(`Deleted ${result.deleted_chunks} chunks`);
   */
  async deleteDocument(source) {
    return this.delete(`/ingest/documents/${encodeURIComponent(source)}`);
  }

  /**
   * Delete a document by ID
   * @param {number} documentId - Document ID
   * @returns {Promise<Object>} Deletion result
   * @throws {APIError} If deletion fails
   */
  async deleteDocumentById(documentId) {
    return this.delete(`/ingest/documents/${documentId}`);
  }

  // ========================================================================
  // Status and Health Endpoints
  // ========================================================================

  /**
   * Get system health status
   * @returns {Promise<{status: string, database_connected: boolean, ollama_available: boolean}>} Health status
   * @throws {APIError} If health check fails
   * 
   * @example
   * const health = await client.getStatus();
   * if (health.status === 'healthy') {
   *   console.log('System is healthy');
   * }
   */
  async getStatus() {
    return this.get('/health');
  }

  /**
   * Get database statistics
   * @returns {Promise<{total_chunks: number, unique_sources: number, unique_models: number}>} Database stats
   * @throws {APIError} If retrieval fails
   */
  async getDatabaseStats() {
    return this.get('/stats');
  }

  /**
   * Get agent status and configuration
   * @returns {Promise<Object>} Agent status with LLM and embedding info
   * @throws {APIError} If retrieval fails
   * 
   * @example
   * const status = await client.getAgentStatus();
   * console.log(status.configuration); // { max_iterations, min_confidence, ... }
   */
  async getAgentStatus() {
    return this.get('/agent/status');
  }

  /**
   * Get database connection and performance stats
   * @returns {Promise<Object>} Detailed database status
   * @throws {APIError} If retrieval fails
   */
  async getDatabaseStatus() {
    return this.get('/database/status');
  }

  /**
   * Run database cleanup tasks
   * @returns {Promise<{success: boolean, orphaned_chunks: number, failed_documents: number}>} Cleanup result
   * @throws {APIError} If cleanup fails
   */
  async runCleanup() {
    return this.post('/cleanup', {});
  }

  /**
   * Reset the entire database (DESTRUCTIVE)
   * @returns {Promise<{success: boolean, message: string, deleted_chunks: number}>} Reset result
   * @throws {APIError} If reset fails
   * 
   * @example
   * const result = await client.resetDatabase();
   * console.log(`Deleted ${result.deleted_chunks} chunks`);
   */
  async resetDatabase() {
    return this.delete('/reset');
  }

  // ========================================================================
  // Helper Methods
  // ========================================================================

  /**
   * Create fetch options with progress tracking
   * @private
   * @param {Function} onProgress - Progress callback (percent: number)
   * @returns {Object} Fetch options
   */
  _createProgressFetchOptions(onProgress) {
    return {
      onProgress: (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onProgress(percent);
        }
      }
    };
  }

  /**
   * Add request interceptor
   * @param {Function} interceptor - Interceptor function
   * @returns {Function} Deregister function
   */
  addRequestInterceptor(interceptor) {
    const originalRequest = this.request.bind(this);
    this.request = async (method, endpoint, options) => {
      const modifiedOptions = await interceptor(
        { method, endpoint, options }
      );
      return originalRequest(method, endpoint, modifiedOptions || options);
    };

    return () => {
      this.request = originalRequest;
    };
  }

  /**
   * Add response interceptor
   * @param {Function} interceptor - Interceptor function
   * @returns {Function} Deregister function
   */
  addResponseInterceptor(interceptor) {
    const originalFetch = this._fetch.bind(this);
    this._fetch = async (url, config) => {
      const response = await originalFetch(url, config);
      return await interceptor(response) || response;
    };

    return () => {
      this._fetch = originalFetch;
    };
  }

  /**
   * Add error handler interceptor
   * @param {Function} handler - Error handler function
   * @returns {Function} Deregister function
   */
  addErrorInterceptor(handler) {
    const originalFetch = this._fetch.bind(this);
    this._fetch = async (url, config) => {
      try {
        return await originalFetch(url, config);
      } catch (error) {
        const handled = await handler(error);
        if (handled) {
          return handled;
        }
        throw error;
      }
    };

    return () => {
      this._fetch = originalFetch;
    };
  }

  /**
   * Batch multiple API calls
   * @param {Array<{method: string, endpoint: string, body?: Object}>} calls - API calls to batch
   * @param {Object} [options={}] - Batch options
   * @returns {Promise<Array>} Results for each call
   * 
   * @example
   * const results = await client.batch([
   *   { method: 'get', endpoint: '/health' },
   *   { method: 'get', endpoint: '/stats' },
   *   { method: 'post', endpoint: '/query/agentic', body: { query: '...' } }
   * ]);
   */
  async batch(calls, options = {}) {
    const parallel = options.parallel ?? true;
    const promises = calls.map(call => {
      const method = call.method.toLowerCase();
      if (method === 'get') {
        return this.get(call.endpoint);
      } else if (method === 'post') {
        return this.post(call.endpoint, call.body || {});
      } else if (method === 'delete') {
        return this.delete(call.endpoint);
      }
      return Promise.reject(new Error(`Unsupported method: ${method}`));
    });

    if (parallel) {
      return Promise.all(promises);
    } else {
      const results = [];
      for (const promise of promises) {
        results.push(await promise);
      }
      return results;
    }
  }
}

/**
 * APIError - Custom error class for API errors
 */
class APIError extends Error {
  /**
   * Create an API error
   * @param {number} status - HTTP status code
   * @param {string} message - Error message
   * @param {Object} [details={}] - Additional error details
   */
  constructor(status, message, details = {}) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.detail = details.detail || details.message;
    this.originalError = details.originalError;
    Object.setPrototypeOf(this, APIError.prototype);
  }

  /**
   * Check if error is a network error
   * @returns {boolean}
   */
  isNetworkError() {
    return this.status === 0;
  }

  /**
   * Check if error is a timeout
   * @returns {boolean}
   */
  isTimeout() {
    return this.message === 'AbortError' || this.message.includes('timeout');
  }

  /**
   * Check if error is a client error (4xx)
   * @returns {boolean}
   */
  isClientError() {
    return this.status >= 400 && this.status < 500;
  }

  /**
   * Check if error is a server error (5xx)
   * @returns {boolean}
   */
  isServerError() {
    return this.status >= 500;
  }

  /**
   * Convert error to JSON
   * @returns {Object}
   */
  toJSON() {
    return {
      status: this.status,
      message: this.message,
      detail: this.detail,
      name: this.name
    };
  }
}

// Export for use as module
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { APIClient, APIError };
}

// Make available globally in browser
if (typeof window !== 'undefined') {
  window.APIClient = APIClient;
  window.APIError = APIError;
}
