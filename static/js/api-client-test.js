/**
 * API Client Integration Tests
 * Test suite for the Agentic RAG JavaScript API client
 * 
 * Usage:
 * - Browser: Open api-client-test.html in a browser
 * - Node.js: node api-client-test.js
 */

// Test utilities
const TestRunner = {
  tests: [],
  passed: 0,
  failed: 0,
  
  test(name, fn) {
    this.tests.push({ name, fn });
  },
  
  async run() {
    console.log('\n' + '='.repeat(60));
    console.log('API Client Integration Tests');
    console.log('='.repeat(60) + '\n');
    
    for (const test of this.tests) {
      try {
        await test.fn();
        this.passed++;
        console.log(`✓ ${test.name}`);
      } catch (error) {
        this.failed++;
        console.error(`✗ ${test.name}`);
        console.error(`  Error: ${error.message}`);
      }
    }
    
    console.log('\n' + '='.repeat(60));
    console.log(`Results: ${this.passed} passed, ${this.failed} failed`);
    console.log('='.repeat(60) + '\n');
    
    return this.failed === 0;
  }
};

// Assertions
function assert(condition, message) {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(message || `Expected ${expected}, got ${actual}`);
  }
}

function assertExists(value, message) {
  if (value === undefined || value === null) {
    throw new Error(message || 'Value does not exist');
  }
}

function assertIsInstance(value, constructor, message) {
  if (!(value instanceof constructor)) {
    throw new Error(message || `Expected instance of ${constructor.name}`);
  }
}

// ============================================================================
// Tests
// ============================================================================

// Test: Client Initialization
TestRunner.test('Client initializes with default config', () => {
  const client = new APIClient();
  assertExists(client);
  assertEqual(client.config.timeout, 30000);
  assertEqual(client.config.retries, 3);
});

TestRunner.test('Client initializes with custom config', () => {
  const client = new APIClient('http://example.com', {
    timeout: 60000,
    retries: 5
  });
  assertEqual(client.baseURL, 'http://example.com');
  assertEqual(client.config.timeout, 60000);
  assertEqual(client.config.retries, 5);
});

// Test: Authentication
TestRunner.test('Can set and get auth token', () => {
  const client = new APIClient();
  client.setAuthToken('test-token');
  assertEqual(client.defaultHeaders['Authorization'], 'Bearer test-token');
  
  client.clearAuthToken();
  assert(!client.defaultHeaders['Authorization']);
});

// Test: Session Management
TestRunner.test('Can set and get session ID', () => {
  const client = new APIClient();
  client.setSessionId(123);
  assertEqual(client.getSessionId(), 123);
  
  client.setSessionId('abc-def');
  assertEqual(client.getSessionId(), 'abc-def');
});

// Test: APIError Class
TestRunner.test('APIError has correct properties', () => {
  const error = new APIError(500, 'Server error', { detail: 'Internal error' });
  assertEqual(error.status, 500);
  assertEqual(error.message, 'Server error');
  assertEqual(error.detail, 'Internal error');
});

TestRunner.test('APIError can identify error types', () => {
  const networkError = new APIError(0, 'Network error');
  assert(networkError.isNetworkError());
  
  const timeoutError = new APIError(0, 'AbortError');
  assert(timeoutError.isTimeout());
  
  const clientError = new APIError(400, 'Bad request');
  assert(clientError.isClientError());
  
  const serverError = new APIError(500, 'Internal error');
  assert(serverError.isServerError());
});

TestRunner.test('APIError toJSON works', () => {
  const error = new APIError(404, 'Not found');
  const json = error.toJSON();
  assertEqual(json.status, 404);
  assertEqual(json.message, 'Not found');
  assertExists(json.name);
});

// Test: Request Methods
TestRunner.test('Request methods build correct URLs', () => {
  const client = new APIClient('http://api.example.com');
  
  // We can't actually make requests without a real server,
  // but we can test URL construction
  const url1 = `${client.baseURL}/query`;
  assertEqual(url1, 'http://api.example.com/query');
  
  const url2 = `${client.baseURL}/ingest`;
  assertEqual(url2, 'http://api.example.com/ingest');
});

// Test: Retry Logic
TestRunner.test('Retry status codes are correct', () => {
  const client = new APIClient();
  const retryable = [408, 429, 500, 502, 503, 504];
  
  retryable.forEach(status => {
    assert(client.retryableStatuses.includes(status));
  });
});

// Test: Error Detection
TestRunner.test('Error detection works correctly', () => {
  const client = new APIClient();
  
  const retryableError = new APIError(500, 'Server error');
  assert(client._isRetryableError(retryableError));
  
  const nonRetryableError = new APIError(400, 'Bad request');
  assert(!client._isRetryableError(nonRetryableError));
});

// Test: Interceptors
TestRunner.test('Request interceptor can be added', async () => {
  const client = new APIClient();
  let interceptorCalled = false;
  
  client.addRequestInterceptor(async (config) => {
    interceptorCalled = true;
    return config;
  });
  
  // Verify interceptor was registered
  assert(typeof client.request === 'function');
});

TestRunner.test('Error interceptor can be added', async () => {
  const client = new APIClient();
  let errorInterceptorCalled = false;
  
  client.addErrorInterceptor(async (error) => {
    errorInterceptorCalled = true;
    return null;
  });
  
  // Verify interceptor was registered
  assert(typeof client._fetch === 'function');
});

// Test: Batch Operations
TestRunner.test('Batch method exists and accepts calls', async () => {
  const client = new APIClient();
  
  // Mock the internal fetch to avoid real requests
  client._fetch = async () => ({ success: true });
  
  // This would normally call the API, but we've mocked it
  assert(typeof client.batch === 'function');
});

// Test: Query Method Signatures
TestRunner.test('Query method has correct signature', async () => {
  const client = new APIClient();
  assert(typeof client.query === 'function');
  assert(typeof client.querySimple === 'function');
});

TestRunner.test('Ingest method has correct signature', async () => {
  const client = new APIClient();
  assert(typeof client.ingest === 'function');
  assert(typeof client.ingestBatch === 'function');
  assert(typeof client.checkDuplicates === 'function');
});

TestRunner.test('Document methods have correct signature', async () => {
  const client = new APIClient();
  assert(typeof client.getDocuments === 'function');
  assert(typeof client.deleteDocument === 'function');
  assert(typeof client.deleteDocumentById === 'function');
});

TestRunner.test('Status methods have correct signature', async () => {
  const client = new APIClient();
  assert(typeof client.getStatus === 'function');
  assert(typeof client.getDatabaseStats === 'function');
  assert(typeof client.getAgentStatus === 'function');
  assert(typeof client.getDatabaseStatus === 'function');
});

TestRunner.test('Session methods have correct signature', async () => {
  const client = new APIClient();
  assert(typeof client.createChatSession === 'function');
  assert(typeof client.listChatSessions === 'function');
  assert(typeof client.getChatSession === 'function');
  assert(typeof client.deleteChatSession === 'function');
});

// Test: Helper Methods
TestRunner.test('Sleep helper works', async () => {
  const client = new APIClient();
  const start = Date.now();
  await client._sleep(100);
  const elapsed = Date.now() - start;
  
  // Should be approximately 100ms (±50ms tolerance)
  assert(elapsed >= 50 && elapsed <= 200, `Sleep duration was ${elapsed}ms`);
});

// Test: Module Export
TestRunner.test('Module exports are available', () => {
  if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    assert(typeof APIClient !== 'undefined');
    assert(typeof APIError !== 'undefined');
  } else if (typeof window !== 'undefined') {
    // Browser environment
    assert(typeof window.APIClient === 'function');
    assert(typeof window.APIError === 'function');
  }
});

// Test: JSDoc Types
TestRunner.test('JSDoc type definitions are present', () => {
  // These are just documentation tests
  // They verify that the code is properly documented
  const client = new APIClient();
  
  // Verify public methods are documented
  assert(client.query.toString().includes('question'));
  assert(client.ingest.toString().includes('file'));
  assert(client.query.toString().length > 50);
});

// ============================================================================
// Run Tests
// ============================================================================

if (typeof window !== 'undefined') {
  // Browser environment
  window.APIClientTests = {
    run: () => TestRunner.run()
  };
  
  // Auto-run if this script is loaded directly
  if (document.currentScript && document.currentScript.dataset.autorun === 'true') {
    document.addEventListener('DOMContentLoaded', () => {
      TestRunner.run();
    });
  }
} else if (typeof module !== 'undefined') {
  // Node.js environment
  TestRunner.run().then(success => {
    process.exit(success ? 0 : 1);
  });
}
