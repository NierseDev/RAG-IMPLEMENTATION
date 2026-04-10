/**
 * State Manager Unit Tests
 * Basic tests to verify state manager functionality
 */

class StateManagerTests {
    constructor() {
        this.passed = 0;
        this.failed = 0;
        this.tests = [];
    }

    test(name, fn) {
        this.tests.push({ name, fn });
    }

    async run() {
        console.log('🧪 Running State Manager Tests...\n');

        for (const { name, fn } of this.tests) {
            try {
                await fn();
                this.passed++;
                console.log(`✅ ${name}`);
            } catch (error) {
                this.failed++;
                console.error(`❌ ${name}`);
                console.error(`   Error: ${error.message}\n`);
            }
        }

        console.log(`\n📊 Results: ${this.passed} passed, ${this.failed} failed\n`);
    }

    assert(condition, message) {
        if (!condition) throw new Error(message);
    }

    assertEqual(a, b, message) {
        if (a !== b) throw new Error(`${message} (expected ${b}, got ${a})`);
    }

    assertDeepEqual(a, b, message) {
        if (JSON.stringify(a) !== JSON.stringify(b)) {
            throw new Error(`${message} (expected ${JSON.stringify(b)}, got ${JSON.stringify(a)})`);
        }
    }
}

// Create test suite
const tests = new StateManagerTests();

// ========== STATE TESTS ==========

tests.test('Initialize state manager', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    const state = sm.getState();
    this.assert(state.chat, 'Chat state exists');
    this.assert(state.document, 'Document state exists');
    this.assert(state.debug, 'Debug state exists');
    this.assert(state.ui, 'UI state exists');
    sm.destroy();
});

tests.test('Get entire state', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    const state = sm.getState();
    this.assert(typeof state === 'object', 'State is an object');
    this.assert(Array.isArray(state.chat.messages), 'Messages is an array');
    sm.destroy();
});

tests.test('Get state by path', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    const messages = sm.getState('chat.messages');
    this.assert(Array.isArray(messages), 'Can get chat.messages');
    
    const session = sm.getState('chat.currentSession');
    this.assertEqual(session, null, 'Can get nested value');
    
    sm.destroy();
});

tests.test('Set state with path', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    sm.setState('chat.currentSession', 'session-1');
    
    const session = sm.getState('chat.currentSession');
    this.assertEqual(session, 'session-1', 'Session updated correctly');
    
    sm.destroy();
});

tests.test('Set state with object', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    sm.setState({
        'chat.currentSession': 'session-1',
        'ui.activeTab': 'ingest'
    });
    
    const session = sm.getState('chat.currentSession');
    const tab = sm.getState('ui.activeTab');
    this.assertEqual(session, 'session-1', 'Session updated');
    this.assertEqual(tab, 'ingest', 'Tab updated');
    
    sm.destroy();
});

tests.test('Deep merge objects', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    
    sm.setState('debug.systemStatus', {
        agentHealthy: true,
        dbHealthy: false
    });
    
    sm.setState('debug.systemStatus', {
        llmModel: 'gpt-4'
    });
    
    const status = sm.getState('debug.systemStatus');
    this.assertEqual(status.agentHealthy, true, 'Previous property preserved');
    this.assertEqual(status.dbHealthy, false, 'Previous property preserved');
    this.assertEqual(status.llmModel, 'gpt-4', 'New property added');
    
    sm.destroy();
});

// ========== SUBSCRIBER TESTS ==========

tests.test('Subscribe to state changes', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    let callCount = 0;
    
    const unsubscribe = sm.subscribe(() => {
        callCount++;
    });
    
    sm.setState('chat.currentSession', 'session-1');
    
    this.assert(callCount > 0, 'Subscriber was called');
    unsubscribe();
    
    sm.destroy();
});

tests.test('Subscribe with dependencies', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    let chatCallCount = 0;
    let docCallCount = 0;
    
    sm.subscribe(() => {
        chatCallCount++;
    }, ['chat']);
    
    sm.subscribe(() => {
        docCallCount++;
    }, ['document']);
    
    sm.setState('chat.currentSession', 'session-1');
    // Chat subscriber should be called, not doc subscriber
    
    this.assert(chatCallCount > 0, 'Chat subscriber called');
    
    sm.destroy();
});

tests.test('Unsubscribe', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    let callCount = 0;
    
    const unsubscribe = sm.subscribe(() => {
        callCount++;
    });
    
    sm.setState('chat.currentSession', 'session-1');
    const countAfterFirst = callCount;
    
    unsubscribe();
    sm.setState('chat.currentSession', 'session-2');
    
    this.assertEqual(callCount, countAfterFirst, 'Subscriber not called after unsubscribe');
    
    sm.destroy();
});

// ========== ACTION TESTS ==========

tests.test('Dispatch action', async function() {
    const sm = new StateManager({ persistenceEnabled: false });
    
    await sm.dispatch('clearMessages');
    
    const messages = sm.getState('chat.messages');
    this.assert(Array.isArray(messages), 'clearMessages action executed');
    
    sm.destroy();
});

tests.test('Add message action', async function() {
    const sm = new StateManager({ persistenceEnabled: false });
    
    await sm.dispatch('addMessage', {
        role: 'user',
        content: 'Hello',
        timestamp: new Date().toISOString()
    });
    
    const messages = sm.getState('chat.messages');
    this.assertEqual(messages.length, 1, 'Message added');
    this.assertEqual(messages[0].role, 'user', 'Message role correct');
    
    sm.destroy();
});

tests.test('Set active tab action', async function() {
    const sm = new StateManager({ persistenceEnabled: false });
    
    await sm.dispatch('setActiveTab', 'ingest');
    
    const tab = sm.getState('ui.activeTab');
    this.assertEqual(tab, 'ingest', 'Active tab updated');
    
    sm.destroy();
});

tests.test('Toggle sidebar action', async function() {
    const sm = new StateManager({ persistenceEnabled: false });
    
    const before = sm.getState('ui.sidebarOpen');
    await sm.dispatch('toggleSidebar');
    const after = sm.getState('ui.sidebarOpen');
    
    this.assertEqual(after, !before, 'Sidebar toggled');
    
    sm.destroy();
});

// ========== RESET TEST ==========

tests.test('Reset state', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    
    sm.setState('chat.currentSession', 'session-1');
    sm.setState('ui.activeTab', 'ingest');
    
    sm.reset();
    
    const session = sm.getState('chat.currentSession');
    const tab = sm.getState('ui.activeTab');
    
    this.assertEqual(session, null, 'Session reset to null');
    this.assertEqual(tab, 'chat', 'Tab reset to default');
    
    sm.destroy();
});

// ========== MIDDLEWARE TESTS ==========

tests.test('Middleware execution', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    let middlewareCalled = false;
    
    sm.use((updates, state) => {
        middlewareCalled = true;
    });
    
    sm.setState('chat.currentSession', 'session-1');
    
    this.assert(middlewareCalled, 'Middleware was called');
    
    sm.destroy();
});

tests.test('Multiple middleware', function() {
    const sm = new StateManager({ persistenceEnabled: false });
    let count = 0;
    
    sm.use(() => count++);
    sm.use(() => count++);
    sm.use(() => count++);
    
    sm.setState('chat.currentSession', 'session-1');
    
    this.assertEqual(count, 3, 'All middleware called');
    
    sm.destroy();
});

// ========== HOOK TESTS ==========

tests.test('StateHooks.useState', function(done) {
    window.StateManagerInstance = new StateManager({ persistenceEnabled: false });
    
    let callCount = 0;
    StateHooks.useState('chat.messages', (messages) => {
        callCount++;
    });
    
    this.assert(callCount > 0, 'useState callback called');
    window.StateManagerInstance.destroy();
});

tests.test('StateHooks.useDispatch', async function() {
    window.StateManagerInstance = new StateManager({ persistenceEnabled: false });
    
    const setTab = StateHooks.useDispatch('setActiveTab');
    await setTab('ingest');
    
    const tab = window.StateManagerInstance.getState('ui.activeTab');
    this.assertEqual(tab, 'ingest', 'useDispatch worked');
    
    window.StateManagerInstance.destroy();
});

tests.test('StateHooks.useSelector', function() {
    window.StateManagerInstance = new StateManager({ persistenceEnabled: false });
    
    let selectedValue;
    StateHooks.useSelector('chat.messages', (value) => {
        selectedValue = value;
    });
    
    this.assert(Array.isArray(selectedValue), 'useSelector returned correct value');
    
    window.StateManagerInstance.destroy();
});

tests.test('StateHooks.useEffect', function() {
    window.StateManagerInstance = new StateManager({ persistenceEnabled: false });
    
    let callCount = 0;
    StateHooks.useEffect((state) => {
        callCount++;
    }, ['chat', 'document']);
    
    this.assert(callCount > 0, 'useEffect callback called');
    
    window.StateManagerInstance.destroy();
});

// ========== RUN TESTS ==========

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => tests.run());
} else {
    tests.run();
}
