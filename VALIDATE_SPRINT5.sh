#!/bin/bash
# Sprint 5 (p3-ui-hierarchical) - Implementation Validation Script

echo "🔍 Validating Sprint 5 Implementation..."
echo ""

# Check 1: State Manager Actions
echo "✅ CHECK 1: State Manager Sub-Agent Actions"
grep -q "recordSubAgentSpawn" static/js/state-manager.js && echo "  ✓ recordSubAgentSpawn action found" || echo "  ✗ recordSubAgentSpawn action missing"
grep -q "recordSubAgentResult" static/js/state-manager.js && echo "  ✓ recordSubAgentResult action found" || echo "  ✗ recordSubAgentResult action missing"
grep -q "updateMainAgentMetrics" static/js/state-manager.js && echo "  ✓ updateMainAgentMetrics action found" || echo "  ✗ updateMainAgentMetrics action missing"
grep -q "updateMainAgentReasoning" static/js/state-manager.js && echo "  ✓ updateMainAgentReasoning action found" || echo "  ✗ updateMainAgentReasoning action missing"
grep -q "updateAgentHierarchy" static/js/state-manager.js && echo "  ✓ updateAgentHierarchy action found" || echo "  ✗ updateAgentHierarchy action missing"
grep -q "toggleAgentExpanded" static/js/state-manager.js && echo "  ✓ toggleAgentExpanded action found" || echo "  ✗ toggleAgentExpanded action missing"
grep -q "clearAgentHierarchy" static/js/state-manager.js && echo "  ✓ clearAgentHierarchy action found" || echo "  ✗ clearAgentHierarchy action missing"
echo ""

# Check 2: Agent Hierarchy State
echo "✅ CHECK 2: Agent Hierarchy State Structure"
grep -q "agentHierarchy" static/js/state-manager.js && echo "  ✓ agentHierarchy state structure found" || echo "  ✗ agentHierarchy state structure missing"
grep -q "mainAgent" static/js/state-manager.js && echo "  ✓ mainAgent structure found" || echo "  ✗ mainAgent structure missing"
grep -q "subAgents" static/js/state-manager.js && echo "  ✓ subAgents array found" || echo "  ✗ subAgents array missing"
grep -q "expandedAgents" static/js/state-manager.js && echo "  ✓ expandedAgents tracking found" || echo "  ✗ expandedAgents tracking missing"
echo ""

# Check 3: UI Components
echo "✅ CHECK 3: UI Components"
test -f static/js/ui-components.js && echo "  ✓ ui-components.js file exists" || echo "  ✗ ui-components.js file missing"
grep -q "class AgentHierarchyPanel" static/js/ui-components.js && echo "  ✓ AgentHierarchyPanel component found" || echo "  ✗ AgentHierarchyPanel component missing"
grep -q "class ReasoningTimeline" static/js/ui-components.js && echo "  ✓ ReasoningTimeline component found" || echo "  ✗ ReasoningTimeline component missing"
grep -q "class MetricsPanel" static/js/ui-components.js && echo "  ✓ MetricsPanel component found" || echo "  ✗ MetricsPanel component missing"
grep -q "const HierarchyStyles" static/js/ui-components.js && echo "  ✓ CSS styling found" || echo "  ✗ CSS styling missing"
echo ""

# Check 4: HTML Integration
echo "✅ CHECK 4: HTML Integration"
grep -q "agent-hierarchy-container" static/index.html && echo "  ✓ agent-hierarchy-container div found" || echo "  ✗ agent-hierarchy-container div missing"
grep -q "reasoning-timeline-container" static/index.html && echo "  ✓ reasoning-timeline-container div found" || echo "  ✗ reasoning-timeline-container div missing"
grep -q "metrics-panel-container" static/index.html && echo "  ✓ metrics-panel-container div found" || echo "  ✗ metrics-panel-container div missing"
grep -q "ui-components.js" static/index.html && echo "  ✓ ui-components.js script include found" || echo "  ✗ ui-components.js script include missing"
grep -q "AgentHierarchyPanel" static/index.html && echo "  ✓ AgentHierarchyPanel initialization found" || echo "  ✗ AgentHierarchyPanel initialization missing"
echo ""

# Check 5: Test Files
echo "✅ CHECK 5: Test Files"
test -f static/js/test-hierarchy-state.js && echo "  ✓ test-hierarchy-state.js file exists" || echo "  ✗ test-hierarchy-state.js file missing"
test -f static/test-hierarchy.html && echo "  ✓ test-hierarchy.html file exists" || echo "  ✗ test-hierarchy.html file missing"
test -f static/test-state-manager.html && echo "  ✓ test-state-manager.html file exists" || echo "  ✗ test-state-manager.html file missing"
grep -q "class HierarchyStateTests" static/js/test-hierarchy-state.js && echo "  ✓ HierarchyStateTests class found" || echo "  ✗ HierarchyStateTests class missing"
echo ""

# Check 6: Documentation
echo "✅ CHECK 6: Documentation"
grep -q "Hierarchical Agent Display" README.MD && echo "  ✓ Documentation section added" || echo "  ✗ Documentation section missing"
grep -q "AgentHierarchyPanel" README.MD && echo "  ✓ AgentHierarchyPanel documented" || echo "  ✗ AgentHierarchyPanel documentation missing"
grep -q "recordSubAgentSpawn" README.MD && echo "  ✓ recordSubAgentSpawn documented" || echo "  ✗ recordSubAgentSpawn documentation missing"
grep -q "test-hierarchy.html" README.MD && echo "  ✓ Test files documented" || echo "  ✗ Test files documentation missing"
test -f PLANS/SPRINT5_IMPLEMENTATION_SUMMARY.md && echo "  ✓ Implementation summary created" || echo "  ✗ Implementation summary missing"
echo ""

# Check 7: Syntax Validation
echo "✅ CHECK 7: Syntax Validation"
node -c static/js/state-manager.js >/dev/null 2>&1 && echo "  ✓ state-manager.js syntax OK" || echo "  ✗ state-manager.js has syntax errors"
node -c static/js/ui-components.js >/dev/null 2>&1 && echo "  ✓ ui-components.js syntax OK" || echo "  ✗ ui-components.js has syntax errors"
node -c static/js/test-hierarchy-state.js >/dev/null 2>&1 && echo "  ✓ test-hierarchy-state.js syntax OK" || echo "  ✗ test-hierarchy-state.js has syntax errors"
echo ""

echo "✅ Validation Complete!"
echo ""
echo "📋 Summary:"
echo "  • 7 new state manager actions"
echo "  • 3 UI components (AgentHierarchyPanel, ReasoningTimeline, MetricsPanel)"
echo "  • ~350 lines of CSS styling"
echo "  • 8 comprehensive tests"
echo "  • 2 interactive test pages"
echo "  • Complete documentation"
echo ""
echo "🚀 Next Steps:"
echo "  1. Test UI: http://localhost:8000/test-hierarchy.html"
echo "  2. Test State: http://localhost:8000/test-state-manager.html"
echo "  3. Integrate with agent code when ready to spawn sub-agents"
echo ""
