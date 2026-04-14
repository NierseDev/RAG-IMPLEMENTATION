"""
Main FastAPI application for Agentic RAG system.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import logging
from pathlib import Path

from app.core.config import settings
from app.api import ingest, query, admin

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="""
    Agentic RAG API with multi-step reasoning and verification.
    
    ## Features
    - 🤖 Agentic reasoning loop with self-reflection
    - 🔍 Vector-based semantic search
    - ✅ Hallucination detection and verification
    - 📄 Multi-format document processing (PDF, DOCX, PPTX, etc.)
    - �� Iterative query refinement
    
    ## Workflow
    1. **Ingest** documents to build knowledge base
    2. **Query** with agentic reasoning for complex questions
    3. **Verify** answers are grounded in retrieved context
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(admin.router)
app.include_router(ingest.router)
app.include_router(query.router)

# Serve static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the home page."""
    html_path = static_path / "home.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding='utf-8'), status_code=200)
    else:
        return HTMLResponse(
            content="""
            <html>
                <head><title>Agentic RAG API</title></head>
                <body>
                    <h1>Agentic RAG API</h1>
                    <p>Welcome to the Agentic RAG system!</p>
                    <ul>
                        <li><a href="/chat">Agentic Chat</a></li>
                        <li><a href="/ingest">Document Ingestion</a></li>
                        <li><a href="/docs">API Documentation (Swagger)</a></li>
                        <li><a href="/redoc">API Documentation (ReDoc)</a></li>
                        <li><a href="/debug">Debug Console (Legacy)</a></li>
                        <li><a href="/health">Health Check</a></li>
                        <li><a href="/stats">Database Stats</a></li>
                    </ul>
                </body>
            </html>
            """,
            status_code=200
        )


@app.get("/chat", response_class=HTMLResponse)
async def chat_interface():
    """Serve the agentic chat interface."""
    html_path = static_path / "chat.html"
    if html_path.exists():
        return HTMLResponse(
            content=html_path.read_text(encoding='utf-8'),
            status_code=200,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    else:
        return HTMLResponse(
            content="<html><body><h1>Chat interface not found</h1></body></html>",
            status_code=404
        )


@app.get("/ingest", response_class=HTMLResponse)
async def ingest_interface():
    """Serve the document ingestion interface."""
    html_path = static_path / "ingest.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding='utf-8'), status_code=200)
    else:
        return HTMLResponse(
            content="<html><body><h1>Ingestion interface not found</h1></body></html>",
            status_code=404
        )


@app.get("/debug", response_class=HTMLResponse)
async def debug_console():
    """Serve the legacy debug console."""
    debug_path = static_path / "debug.html"
    if debug_path.exists():
        return HTMLResponse(content=debug_path.read_text(encoding='utf-8'), status_code=200)
    else:
        return HTMLResponse(
            content="<html><body><h1>Debug console not found</h1></body></html>",
            status_code=404
        )


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("="*60)
    logger.info(f"Starting {settings.api_title} v{settings.api_version}")
    logger.info(f"Ollama LLM: {settings.ollama_llm_model}")
    logger.info(f"Ollama Embeddings: {settings.ollama_embed_model}")
    logger.info(f"Max Agent Iterations: {settings.max_agent_iterations}")
    logger.info(f"Min Confidence: {settings.min_confidence_threshold}")
    logger.info("="*60)


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down Agentic RAG API")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug_mode
    )
