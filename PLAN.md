IMPORTANT:
THIS PLAN IS FOR AN AGENTIC RAG API IMPLEMENTATION DURING DEVELOPMENT,
WE WILL BE TESTING THE AGENT THRU A WEB INTERFACE.



Plan 1, Revisit Agents for Local / Cloud


Phase 1, Research Local and Cloud Agents

- Local Agents (Two Types)
-- High-Performance / Highly Efficient thru CPU (PRIORITY)
--- Current Model: qwen3.5:4b and mxbai-embed-large

PRIORITY is to find a balance that can handle Agentic RAG Requests at a lower cost and processing time.
For this Machine Specs, CPU is a AMD Ryzen 5 8600G.

-- High-Performance / Highly Efficient thru GPU

Same Priority but more emphasis on Performance to make use of the GPU.


- Cloud Agents (Two Types)
-- Best performing RAG Agent at a low cost.

-- Best performaing RAG Agent at a balanced cost.

Explore Agents for the Main LLM and planned Sub-Agents.



Phase 2, REDO Debug Application Shell

TWO TABS

1. Agentic Chat with Chat History on the Left Side Bar and Debug Tools on the Right Side Bar.
1.2. Debug Tools must also contain statuses of the Database and Agent.
1.3. Non-Functional (Planned Implementation in the next Phase),
1.3.1. File Uploader Button and Modal for Document Injestion.

2. Document Injestion
2.1. File/s Upload Box for Single or Batch Document Processing.
2.2. Limit to what Docling can Process
2.3. History of all uploaded documents (REFER TO PHASE 2.5 FOR RECORD MANAGEMENT TO PREVENT DUPLICATES AND PROCESS ONLY WHAT IS NEW)

Phase 2.5, DOCLING AND DOCUMENT INJESTION RETROFIT AND OPTIMIZATION

RULES:
IMPORTANT: DON'T OVER-ENGINEER IT.
1. Safe and Fast O(1) Document Injestion.
2. Optimize Injestion for Agents Context Tokens on both Local and Cloud.
2.1. Understand Document parsing challenges, format considerations.
3. Record Management to prevent DUPLICATE Document Uploads, Create a Schema for a new table on Supabase.
3.1 Understand why naive ingestion duplicates, incremental updates.
4. Verify Metadata Extraction and if it exists, enhance retrieval for the Agents. Create a Schema for a new table on Supabase.
5. Hybrid Search. Keyword + vector search, RRF combination, reranking.
5.1. Understand why vector alone isn't enough, hybrid strategies, reranking


Phase 3, Additional Tools and Sub-Agents

- Additional Tools:
--  Text-to-SQL tool (query structured data)
--  Web search fallback (when docs don't have the answer)
--- Understand Multi-tool agents, routing between structured/unstructured data, graceful fallbacks, attribution for trust


- Sub-Agents:
-- Detect full-document scenarios, spawn isolated sub-agent with its own tools, nested tool call display in UI, show reasoning from both main agent and sub-agents.
--- Understand Context management, agent delegation, hierarchical agent display, when to isolate.
