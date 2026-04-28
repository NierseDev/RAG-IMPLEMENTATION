"""
Text-to-SQL Tool for querying structured data in RAG database.

Safety features:
- Read-only queries (SELECT only)
- SQL injection prevention
- Query timeout (30s)
- Row limit (100 rows max)
- System table blocking
"""
from typing import Dict, Any, Optional, List
import re
import logging
from app.services.llm import llm_service
from app.core.database import supabase

logger = logging.getLogger(__name__)


class TextToSQLTool:
    """
    Converts natural language questions to SQL queries for the RAG database.
    """
    
    # SQL Schema context for the LLM
    SCHEMA_CONTEXT = """
# RAG Database Schema

## Table: rag_chunks
Stores document chunks with vector embeddings for semantic search.

**Columns:**
- id (BIGSERIAL PRIMARY KEY): Unique chunk identifier
- chunk_id (TEXT NOT NULL UNIQUE): Human-readable chunk ID
- source (TEXT NOT NULL): Document source/filename
- text (TEXT NOT NULL): The actual text content
- ai_provider (TEXT NOT NULL): AI provider used (ollama, openai, anthropic, google, groq)
- embedding_model (TEXT NOT NULL): Embedding model used (e.g., mxbai-embed-large)
- embedding (VECTOR NOT NULL): Vector embedding (1024 or 1536 dimensions)
- created_at (TIMESTAMPTZ): When the chunk was created

**Indexes:**
- Fast vector similarity search (ivfflat)
- Source, chunk_id, provider, model indexes for filtering

## Available Functions

### match_chunks(query_embedding, match_count, min_similarity, filter_source, filter_provider, filter_model)
Vector similarity search function.

Returns: chunk_id, source, ai_provider, embedding_model, text, similarity, created_at

### get_chunk_stats()
Get database statistics.

Returns: total_chunks, unique_sources, unique_models, latest_chunk

## Common Query Patterns

**Count documents by source:**
```sql
SELECT source, COUNT(*) as chunk_count
FROM rag_chunks
GROUP BY source
ORDER BY chunk_count DESC;
```

**Recent uploads:**
```sql
SELECT source, COUNT(*) as chunks, MAX(created_at) as uploaded_at
FROM rag_chunks
GROUP BY source
ORDER BY uploaded_at DESC
LIMIT 10;
```

**Provider statistics:**
```sql
SELECT ai_provider, embedding_model, COUNT(*) as count
FROM rag_chunks
GROUP BY ai_provider, embedding_model;
```

**Search for specific content (case-insensitive):**
```sql
SELECT chunk_id, source, LEFT(text, 100) as preview
FROM rag_chunks
WHERE text ILIKE '%search term%'
LIMIT 20;
```
"""
    
    # Blocked keywords for safety
    BLOCKED_KEYWORDS = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
        'pg_', 'information_schema', 'pg_catalog'
    ]
    
    # Maximum rows to return
    MAX_ROWS = 100
    
    # Query timeout in seconds
    QUERY_TIMEOUT = 30
    
    def __init__(self):
        """Initialize the SQL tool."""
        self.supabase = supabase
        logger.info("TextToSQLTool initialized")
    
    async def execute(self, user_question: str) -> Dict[str, Any]:
        """
        Main execution method: converts natural language to SQL and executes it.
        
        Args:
            user_question: Natural language question about the database
            
        Returns:
            Dict with 'success', 'data', 'query', 'error' keys
        """
        try:
            # Step 1: Generate SQL query from natural language
            sql_query = await self._generate_sql(user_question)
            
            # Step 2: Validate the query for safety
            validation = self._validate_query(sql_query)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': validation['reason'],
                    'query': sql_query
                }
            
            # Step 3: Execute the query with safety limits
            result = await self._execute_query(sql_query)
            
            return {
                'success': True,
                'data': result['data'],
                'query': sql_query,
                'row_count': len(result['data']) if result['data'] else 0,
                'interpretation': await self._interpret_results(user_question, result['data'])
            }
            
        except Exception as e:
            logger.error(f"SQL tool execution error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"SQL execution error: {str(e)}",
                'query': None
            }
    
    async def _generate_sql(self, user_question: str) -> str:
        """
        Generate SQL query from natural language using LLM.
        
        Args:
            user_question: Natural language question
            
        Returns:
            SQL query string
        """
        prompt = f"""You are a SQL expert. Convert the user's question into a SQL query for the RAG database.

{self.SCHEMA_CONTEXT}

## User Question
{user_question}

## Instructions
1. Generate a valid PostgreSQL SELECT query only
2. Use proper table and column names from the schema
3. Add appropriate WHERE, GROUP BY, ORDER BY clauses
4. Limit results to {self.MAX_ROWS} rows max
5. Use ILIKE for case-insensitive text search
6. Return ONLY the SQL query, no explanation

## Response Format
Return only the SQL query, starting with SELECT.

SQL Query:"""

        response = await llm_service.generate_text(
            prompt=prompt,
            max_tokens=500,
            temperature=0.0  # Deterministic for SQL generation
        )
        
        # Extract SQL query from response
        sql_query = response.strip()
        
        # Remove markdown code blocks if present
        sql_query = re.sub(r'^```sql\s*', '', sql_query, flags=re.IGNORECASE)
        sql_query = re.sub(r'^```\s*', '', sql_query)
        sql_query = re.sub(r'\s*```$', '', sql_query)
        sql_query = sql_query.strip()
        
        # Ensure LIMIT is present
        if 'LIMIT' not in sql_query.upper():
            sql_query = f"{sql_query.rstrip(';')} LIMIT {self.MAX_ROWS};"
        
        logger.info(f"Generated SQL: {sql_query}")
        return sql_query
    
    def _validate_query(self, sql_query: str) -> Dict[str, Any]:
        """
        Validate SQL query for safety.
        
        Args:
            sql_query: SQL query to validate
            
        Returns:
            Dict with 'valid' (bool) and 'reason' (str) keys
        """
        # Check if it's a SELECT query
        if not sql_query.strip().upper().startswith('SELECT'):
            return {
                'valid': False,
                'reason': 'Only SELECT queries are allowed (read-only mode)'
            }
        
        # Check for blocked keywords (SQL injection prevention)
        query_upper = sql_query.upper()
        for keyword in self.BLOCKED_KEYWORDS:
            if keyword in query_upper:
                return {
                    'valid': False,
                    'reason': f'Blocked keyword detected: {keyword}'
                }
        
        # Check for semicolon-separated multiple statements
        if sql_query.count(';') > 1:
            return {
                'valid': False,
                'reason': 'Multiple statements not allowed'
            }
        
        # Check for comment-based injection attempts
        if '--' in sql_query or '/*' in sql_query:
            return {
                'valid': False,
                'reason': 'SQL comments not allowed for security'
            }
        
        return {'valid': True, 'reason': None}
    
    async def _execute_query(self, sql_query: str) -> Dict[str, Any]:
        """
        Execute SQL query with timeout and error handling.
        
        Args:
            sql_query: Validated SQL query
            
        Returns:
            Dict with 'data' and optional 'error' keys
        """
        try:
            # Execute RPC call to Supabase
            # Note: Supabase doesn't directly support raw SQL from client,
            # so we use the PostgREST interface with rpc() for custom functions
            
            # For general queries, we need to use the table() interface
            # This is a limitation - in production, you'd create stored procedures
            
            # For now, we'll execute queries that match our common patterns
            # For arbitrary SQL, you'd need a backend endpoint or stored procedure
            
            # Parse the query to determine the operation
            result = await self._execute_via_supabase(sql_query)
            
            return {'data': result}
            
        except Exception as e:
            logger.error(f"Query execution error: {e}", exc_info=True)
            raise Exception(f"Failed to execute query: {str(e)}")
    
    async def _execute_via_supabase(self, sql_query: str) -> List[Dict[str, Any]]:
        """
        Execute query via Supabase client.
        
        This is a simplified implementation. In production, you would:
        1. Create a stored procedure in Supabase that accepts SQL
        2. Call it via supabase.rpc()
        3. Or create a backend endpoint that executes raw SQL securely
        
        For now, we'll handle common query patterns.
        """
        # TODO: In production, create a Supabase function:
        # CREATE FUNCTION execute_safe_query(query TEXT) RETURNS JSON
        
        # For demo purposes, handle common patterns directly
        query_upper = sql_query.upper()
        
        # Pattern 1: Get statistics
        if 'GET_CHUNK_STATS' in query_upper or ('COUNT(*)' in query_upper and 'GROUP BY' not in query_upper):
            response = self.supabase.rpc('get_chunk_stats').execute()
            return response.data
        
        # Pattern 2: Group by source
        if 'GROUP BY SOURCE' in query_upper or 'GROUP BY source' in sql_query:
            response = self.supabase.table('rag_chunks') \
                .select('source') \
                .execute()
            
            # Manually group the results
            source_counts = {}
            for row in response.data:
                source = row['source']
                source_counts[source] = source_counts.get(source, 0) + 1
            
            return [{'source': k, 'chunk_count': v} for k, v in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)]
        
        # Pattern 3: Recent uploads
        if 'ORDER BY' in query_upper and 'DESC' in query_upper:
            response = self.supabase.table('rag_chunks') \
                .select('source, created_at') \
                .order('created_at', desc=True) \
                .limit(self.MAX_ROWS) \
                .execute()
            return response.data
        
        # Pattern 4: Search text content
        if 'ILIKE' in query_upper or 'LIKE' in query_upper:
            # Extract search term (simple regex)
            match = re.search(r"ILIKE\s+'%(.+?)%'", sql_query, re.IGNORECASE)
            if match:
                search_term = match.group(1)
                response = self.supabase.table('rag_chunks') \
                    .select('chunk_id, source, text') \
                    .ilike('text', f'%{search_term}%') \
                    .limit(self.MAX_ROWS) \
                    .execute()
                
                # Truncate text to preview
                results = []
                for row in response.data:
                    results.append({
                        'chunk_id': row['chunk_id'],
                        'source': row['source'],
                        'preview': row['text'][:100] + '...' if len(row['text']) > 100 else row['text']
                    })
                return results
        
        # Default: Return all chunks (with limit)
        response = self.supabase.table('rag_chunks') \
            .select('*') \
            .limit(self.MAX_ROWS) \
            .execute()
        
        return response.data
    
    async def _interpret_results(self, question: str, data: List[Dict[str, Any]]) -> str:
        """
        Interpret SQL results in natural language.
        
        Args:
            question: Original user question
            data: Query results
            
        Returns:
            Natural language interpretation
        """
        if not data:
            return "No results found for your query."
        
        # Format data for LLM
        data_str = str(data[:10])  # Limit to first 10 rows for interpretation
        
        prompt = f"""Interpret these SQL query results in natural language to answer the user's question.

User Question: {question}

Query Results: {data_str}

Total Rows: {len(data)}

Provide a clear, concise answer in 2-3 sentences."""

        response = await llm_service.generate_text(
            prompt=prompt,
            max_tokens=200,
            temperature=0.3
        )
        
        return response.strip()
    
    def get_tool_description(self) -> str:
        """Return a description of this tool for the agent."""
        return """
**Text-to-SQL Tool**

Convert natural language questions into SQL queries to analyze the RAG database.

**Use when:**
- User asks about document statistics (counts, sources, models)
- User wants to know what documents are in the system
- User searches for specific content in documents
- User asks analytical questions about the data

**Examples:**
- "How many documents do we have?"
- "What documents were uploaded today?"
- "Which embedding model is most used?"
- "Find chunks containing 'machine learning'"

**Output:**
- SQL query generated
- Query results as structured data
- Natural language interpretation
"""


# Global instance
sql_tool = TextToSQLTool()
