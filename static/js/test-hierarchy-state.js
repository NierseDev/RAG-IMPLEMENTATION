/**
 * Test Suite for Sub-Agent Hierarchy State Management
 * Tests all new actions and state updates for agent hierarchy tracking
 */

class HierarchyStateTests {
    constructor() {
        this.stateManager = null;
        this.testResults = [];
        this.init();
    }

    init() {
        // Create fresh state manager instance for testing
        this.stateManager = new StateManager({ persistenceEnabled: false });
        console.log('🔧 Test Suite Initialized');
    }

    /**
     * Run all tests
     */
    async runAllTests() {
        console.log('\n===== STARTING TEST SUITE =====\n');
        
        await this.testRecordSubAgentSpawn();
        await this.testRecordSubAgentResult();
        await this.testUpdateMainAgentMetrics();
        await this.testUpdateMainAgentReasoning();
        await this.testUpdateAgentHierarchy();
        await this.testToggleAgentExpanded();
        await this.testClearAgentHierarchy();
        await this.testComplexHierarchy();
        
        this.printSummary();
    }

    /**
     * Test recordSubAgentSpawn action
     */
    async testRecordSubAgentSpawn() {
        console.log('📌 TEST: recordSubAgentSpawn');
        
        try {
            const agentId = await this.stateManager.dispatch('recordSubAgentSpawn', {
                agentType: 'full_document',
                context: 'Processing full document scenario',
                reasoning: ['Step 1', 'Step 2']
            });
            
            const hierarchy = this.stateManager.getState('debug.agentHierarchy');
            const subAgent = hierarchy.subAgents[0];
            
            // Assertions
            if (!agentId) throw new Error('No agent ID returned');
            if (!subAgent) throw new Error('Sub-agent not added to hierarchy');
            if (subAgent.type !== 'full_document') throw new Error('Agent type mismatch');
            if (subAgent.status !== 'running') throw new Error('Agent status should be "running"');
            if (subAgent.reasoning.length !== 2) throw new Error('Reasoning not stored correctly');
            if (!subAgent.metrics.startTime) throw new Error('Start time not set');
            
            this.pass('recordSubAgentSpawn');
            console.log('  ✓ Sub-agent spawned correctly');
            console.log(`  ✓ Agent ID: ${agentId}`);
            console.log(`  ✓ Type: ${subAgent.type}`);
            console.log(`  ✓ Status: ${subAgent.status}`);
        } catch (error) {
            this.fail('recordSubAgentSpawn', error.message);
        }
    }

    /**
     * Test recordSubAgentResult action
     */
    async testRecordSubAgentResult() {
        console.log('\n📊 TEST: recordSubAgentResult');
        
        try {
            // First spawn an agent
            const agentId = await this.stateManager.dispatch('recordSubAgentSpawn', {
                agentType: 'comparison',
                context: 'Comparing documents'
            });
            
            // Then complete it
            await this.stateManager.dispatch('recordSubAgentResult', {
                subAgentId: agentId,
                result: 'Found 5 key differences',
                reasoning: ['Analysis 1', 'Analysis 2', 'Analysis 3'],
                metrics: {
                    retrievedDocuments: 8,
                    confidence: 0.85
                }
            });
            
            const hierarchy = this.stateManager.getState('debug.agentHierarchy');
            const subAgent = hierarchy.subAgents.find(a => a.id === agentId);
            
            // Assertions
            if (!subAgent) throw new Error('Sub-agent not found');
            if (subAgent.status !== 'completed') throw new Error('Status should be "completed"');
            if (subAgent.result !== 'Found 5 key differences') throw new Error('Result not stored');
            if (subAgent.reasoning.length !== 3) throw new Error('Reasoning not updated');
            if (!subAgent.metrics.endTime) throw new Error('End time not set');
            if (subAgent.metrics.retrievedDocuments !== 8) throw new Error('Document count not stored');
            if (subAgent.metrics.confidence !== 0.85) throw new Error('Confidence not stored');
            
            this.pass('recordSubAgentResult');
            console.log('  ✓ Sub-agent result recorded correctly');
            console.log(`  ✓ Result: ${subAgent.result}`);
            console.log(`  ✓ Duration: ${subAgent.metrics.duration.toFixed(2)}s`);
            console.log(`  ✓ Metrics updated`);
        } catch (error) {
            this.fail('recordSubAgentResult', error.message);
        }
    }

    /**
     * Test updateMainAgentMetrics action
     */
    async testUpdateMainAgentMetrics() {
        console.log('\n⏱️ TEST: updateMainAgentMetrics');
        
        try {
            await this.stateManager.dispatch('updateMainAgentMetrics', {
                metrics: {
                    duration: 5.5,
                    retrievedDocuments: 12,
                    iterations: 2,
                    confidence: 0.92
                }
            });
            
            const hierarchy = this.stateManager.getState('debug.agentHierarchy');
            const metrics = hierarchy.mainAgent.metrics;
            
            // Assertions
            if (metrics.duration !== 5.5) throw new Error('Duration not updated');
            if (metrics.retrievedDocuments !== 12) throw new Error('Retrieved documents not updated');
            if (metrics.iterations !== 2) throw new Error('Iterations not updated');
            if (metrics.confidence !== 0.92) throw new Error('Confidence not updated');
            
            this.pass('updateMainAgentMetrics');
            console.log('  ✓ Main agent metrics updated correctly');
            console.log(`  ✓ Duration: ${metrics.duration}s`);
            console.log(`  ✓ Confidence: ${(metrics.confidence * 100).toFixed(1)}%`);
        } catch (error) {
            this.fail('updateMainAgentMetrics', error.message);
        }
    }

    /**
     * Test updateMainAgentReasoning action
     */
    async testUpdateMainAgentReasoning() {
        console.log('\n🧠 TEST: updateMainAgentReasoning');
        
        try {
            const reasoning = [
                'Analyzed query for complexity',
                'Detected multi-step scenario',
                'Spawned 2 specialized sub-agents',
                'Aggregated results'
            ];
            
            await this.stateManager.dispatch('updateMainAgentReasoning', {
                reasoning: reasoning
            });
            
            const hierarchy = this.stateManager.getState('debug.agentHierarchy');
            const mainReasoning = hierarchy.mainAgent.reasoning;
            
            // Assertions
            if (mainReasoning.length !== 4) throw new Error('Reasoning length mismatch');
            if (mainReasoning[0] !== reasoning[0]) throw new Error('First reasoning step mismatch');
            if (mainReasoning[3] !== reasoning[3]) throw new Error('Last reasoning step mismatch');
            
            this.pass('updateMainAgentReasoning');
            console.log('  ✓ Main agent reasoning updated correctly');
            console.log(`  ✓ Reasoning steps: ${mainReasoning.length}`);
            mainReasoning.forEach((step, idx) => {
                console.log(`    ${idx + 1}. ${step}`);
            });
        } catch (error) {
            this.fail('updateMainAgentReasoning', error.message);
        }
    }

    /**
     * Test updateAgentHierarchy action
     */
    async testUpdateAgentHierarchy() {
        console.log('\n🌳 TEST: updateAgentHierarchy');
        
        try {
            const newHierarchy = {
                mainAgent: {
                    type: 'main',
                    status: 'completed',
                    reasoning: ['Test reasoning'],
                    metrics: {
                        duration: 10,
                        retrievedDocuments: 20,
                        iterations: 3,
                        confidence: 0.95
                    }
                },
                subAgents: [
                    {
                        id: 'sub1',
                        type: 'full_document',
                        status: 'completed',
                        reasoning: [],
                        result: 'Test result',
                        metrics: { duration: 3 }
                    }
                ],
                expandedAgents: { main: true, sub1: false }
            };
            
            await this.stateManager.dispatch('updateAgentHierarchy', {
                hierarchy: newHierarchy
            });
            
            const hierarchy = this.stateManager.getState('debug.agentHierarchy');
            
            // Assertions
            if (hierarchy.mainAgent.status !== 'completed') throw new Error('Main agent status not updated');
            if (hierarchy.subAgents.length !== 1) throw new Error('Sub-agents not updated');
            if (hierarchy.subAgents[0].type !== 'full_document') throw new Error('Sub-agent type mismatch');
            if (!hierarchy.expandedAgents.main) throw new Error('Expanded state not updated');
            
            this.pass('updateAgentHierarchy');
            console.log('  ✓ Full hierarchy updated correctly');
            console.log(`  ✓ Main agent status: ${hierarchy.mainAgent.status}`);
            console.log(`  ✓ Sub-agents count: ${hierarchy.subAgents.length}`);
        } catch (error) {
            this.fail('updateAgentHierarchy', error.message);
        }
    }

    /**
     * Test toggleAgentExpanded action
     */
    async testToggleAgentExpanded() {
        console.log('\n🔄 TEST: toggleAgentExpanded');
        
        try {
            // Initial state should have main expanded
            let hierarchy = this.stateManager.getState('debug.agentHierarchy');
            const initialState = hierarchy.expandedAgents.main;
            
            // Toggle
            await this.stateManager.dispatch('toggleAgentExpanded', { agentId: 'main' });
            hierarchy = this.stateManager.getState('debug.agentHierarchy');
            
            if (hierarchy.expandedAgents.main === initialState) {
                throw new Error('Toggle did not work');
            }
            
            // Toggle again
            await this.stateManager.dispatch('toggleAgentExpanded', { agentId: 'main' });
            hierarchy = this.stateManager.getState('debug.agentHierarchy');
            
            if (hierarchy.expandedAgents.main !== initialState) {
                throw new Error('Second toggle did not restore state');
            }
            
            this.pass('toggleAgentExpanded');
            console.log('  ✓ Toggle functionality works correctly');
            console.log(`  ✓ Final state: ${hierarchy.expandedAgents.main ? 'expanded' : 'collapsed'}`);
        } catch (error) {
            this.fail('toggleAgentExpanded', error.message);
        }
    }

    /**
     * Test clearAgentHierarchy action
     */
    async testClearAgentHierarchy() {
        console.log('\n🗑️ TEST: clearAgentHierarchy');
        
        try {
            // Add some agents first
            await this.stateManager.dispatch('recordSubAgentSpawn', {
                agentType: 'extraction',
                context: 'Extraction task'
            });
            
            let hierarchy = this.stateManager.getState('debug.agentHierarchy');
            if (hierarchy.subAgents.length === 0) {
                throw new Error('Sub-agent not spawned for test');
            }
            
            // Clear
            await this.stateManager.dispatch('clearAgentHierarchy');
            hierarchy = this.stateManager.getState('debug.agentHierarchy');
            
            // Assertions
            if (hierarchy.subAgents.length !== 0) throw new Error('Sub-agents not cleared');
            if (hierarchy.mainAgent.status !== 'idle') throw new Error('Main agent status not reset');
            if (Object.keys(hierarchy.expandedAgents).length !== 0) throw new Error('Expanded agents not cleared');
            
            this.pass('clearAgentHierarchy');
            console.log('  ✓ Hierarchy cleared correctly');
            console.log('  ✓ Main agent reset to idle');
            console.log('  ✓ All sub-agents removed');
        } catch (error) {
            this.fail('clearAgentHierarchy', error.message);
        }
    }

    /**
     * Test complex multi-level hierarchy scenario
     */
    async testComplexHierarchy() {
        console.log('\n🌳 TEST: Complex Multi-Level Hierarchy');
        
        try {
            // Clear first
            await this.stateManager.dispatch('clearAgentHierarchy');
            
            // Update main agent reasoning
            await this.stateManager.dispatch('updateMainAgentReasoning', {
                reasoning: [
                    'Query received: "Analyze document set"',
                    'Detected complex task requiring multiple perspectives',
                    'Spawning 3 specialized sub-agents'
                ]
            });
            
            // Spawn multiple sub-agents
            const spawnedIds = [];
            const types = ['full_document', 'comparison', 'extraction'];
            
            for (let i = 0; i < 3; i++) {
                const id = await this.stateManager.dispatch('recordSubAgentSpawn', {
                    agentType: types[i],
                    context: `Agent ${i + 1}: ${types[i]} processing`,
                    reasoning: [`Starting ${types[i]} analysis`]
                });
                spawnedIds.push(id);
            }
            
            // Complete agents with different speeds
            for (let i = 0; i < 3; i++) {
                await this.stateManager.dispatch('recordSubAgentResult', {
                    subAgentId: spawnedIds[i],
                    result: `Results from ${types[i]} agent: analysis complete`,
                    reasoning: [
                        `Processing with ${types[i]} strategy`,
                        'Analysis complete',
                        'Returning results'
                    ],
                    metrics: {
                        retrievedDocuments: Math.floor(Math.random() * 10) + 5,
                        confidence: Math.random() * 0.2 + 0.8
                    }
                });
            }
            
            // Update main agent metrics
            await this.stateManager.dispatch('updateMainAgentMetrics', {
                metrics: {
                    duration: 12.5,
                    retrievedDocuments: 28,
                    iterations: 4,
                    confidence: 0.88
                }
            });
            
            // Verify final state
            let hierarchy = this.stateManager.getState('debug.agentHierarchy');
            
            // Assertions
            if (hierarchy.subAgents.length !== 3) throw new Error('Not all sub-agents present');
            if (!hierarchy.subAgents.every(a => a.status === 'completed')) throw new Error('Not all agents completed');
            if (hierarchy.mainAgent.reasoning.length !== 3) throw new Error('Main reasoning not updated');
            if (hierarchy.mainAgent.metrics.duration !== 12.5) throw new Error('Main metrics not updated');
            
            // Count different types
            const typeCounts = {};
            hierarchy.subAgents.forEach(a => {
                typeCounts[a.type] = (typeCounts[a.type] || 0) + 1;
            });
            
            this.pass('Complex Multi-Level Hierarchy');
            console.log('  ✓ Complex hierarchy built successfully');
            console.log(`  ✓ Total sub-agents: ${hierarchy.subAgents.length}`);
            console.log(`  ✓ Agent types breakdown:`);
            Object.entries(typeCounts).forEach(([type, count]) => {
                console.log(`    - ${type}: ${count}`);
            });
            console.log(`  ✓ Main agent confidence: ${(hierarchy.mainAgent.metrics.confidence * 100).toFixed(1)}%`);
        } catch (error) {
            this.fail('Complex Multi-Level Hierarchy', error.message);
        }
    }

    // Helper methods
    pass(testName) {
        this.testResults.push({ name: testName, passed: true });
    }

    fail(testName, error) {
        this.testResults.push({ name: testName, passed: false, error });
        console.error(`  ✗ ${error}`);
    }

    printSummary() {
        console.log('\n===== TEST SUMMARY =====\n');
        
        const passed = this.testResults.filter(t => t.passed).length;
        const total = this.testResults.length;
        const percentage = ((passed / total) * 100).toFixed(1);
        
        console.log(`Results: ${passed}/${total} tests passed (${percentage}%)\n`);
        
        this.testResults.forEach(result => {
            const symbol = result.passed ? '✓' : '✗';
            const status = result.passed ? 'PASS' : 'FAIL';
            console.log(`${symbol} ${result.name}: ${status}`);
            if (result.error) {
                console.log(`  Error: ${result.error}`);
            }
        });
        
        console.log('\n===== END OF TEST SUITE =====\n');
    }
}

// Run tests if this file is executed directly
if (typeof window === 'undefined') {
    // Node.js environment - would need state-manager available
    module.exports = HierarchyStateTests;
} else {
    // Browser environment
    window.HierarchyStateTests = HierarchyStateTests;
}
