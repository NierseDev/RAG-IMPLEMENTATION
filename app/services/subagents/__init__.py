"""
Specialized sub-agents for Agentic RAG (Sprint 5).

Sub-agents are spawned by the main agent for specialized reasoning on:
- Full documents (without chunking)
- Cross-document comparison
- Structured data extraction
"""

from app.services.subagents.full_document_agent import FullDocumentAgent
from app.services.subagents.comparison_agent import ComparisonAgent
from app.services.subagents.extraction_agent import ExtractionAgent

__all__ = [
    'FullDocumentAgent',
    'ComparisonAgent',
    'ExtractionAgent'
]
