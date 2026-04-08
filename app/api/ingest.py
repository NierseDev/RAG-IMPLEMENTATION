"""
Document ingestion endpoints.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List
import tempfile
import os
import time
from app.models.responses import IngestResponse, DocumentListResponse, BatchIngestResponse
from app.services.document_processor import document_processor
from app.core.database import db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@router.post("", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    source: Optional[str] = Form(None)
):
    """
    Ingest a document into the RAG knowledge base.
    Processes the document, creates chunks, and stores with embeddings.
    """
    start_time = time.time()
    
    try:
        # Use filename as source if not provided
        if not source:
            source = file.filename
        
        # Validate file
        file_size = 0
        content = await file.read()
        file_size = len(content)
        
        valid, message = document_processor.validate_file(file.filename, file_size)
        if not valid:
            raise HTTPException(status_code=400, detail=message)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            # Process document
            chunks, metadata = await document_processor.process_document(tmp_path, source)
            
            if not chunks:
                raise HTTPException(status_code=400, detail="No content could be extracted from document")
            
            # Store chunks in database
            inserted = await db.insert_chunks_batch(chunks)
            
            processing_time = time.time() - start_time
            
            return IngestResponse(
                success=True,
                message=f"Document processed successfully",
                source=source,
                chunks_created=inserted,
                file_size=file_size,
                processing_time=processing_time
            )
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting document: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")


@router.post("/check-duplicates")
async def check_duplicates(
    filenames: List[str],
    source_prefix: Optional[str] = None
):
    """
    Check which files already exist in the knowledge base.
    
    Args:
        filenames: List of filenames to check
        source_prefix: Optional prefix to prepend to filenames
        
    Returns:
        Dictionary mapping filenames to their existence status and chunk count
    """
    try:
        results = {}
        for filename in filenames:
            source = f"{source_prefix}/{filename}" if source_prefix else filename
            exists = await db.source_exists(source)
            
            if exists:
                chunk_count = await db.get_source_chunk_count(source)
                results[filename] = {
                    "exists": True,
                    "source": source,
                    "chunk_count": chunk_count
                }
            else:
                results[filename] = {
                    "exists": False,
                    "source": source,
                    "chunk_count": 0
                }
        
        return {
            "success": True,
            "results": results,
            "total_checked": len(filenames),
            "existing": sum(1 for r in results.values() if r["exists"])
        }
    except Exception as e:
        logger.error(f"Error checking duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=BatchIngestResponse)
async def ingest_documents_batch(
    files: List[UploadFile] = File(...),
    source_prefix: Optional[str] = Form(None),
    duplicate_action: Optional[str] = Form("skip")
):
    """
    Ingest multiple documents into the RAG knowledge base.
    Processes all documents, creates chunks, and stores with embeddings.
    
    Args:
        files: List of files to upload
        source_prefix: Optional prefix to prepend to filenames
        duplicate_action: Action for duplicate files - "skip", "replace", or "append" (default: "skip")
    """
    start_time = time.time()
    results = []
    total_chunks = 0
    successful = 0
    failed = 0
    skipped = 0
    
    for file in files:
        file_start = time.time()
        try:
            # Use source prefix + filename or just filename
            source = f"{source_prefix}/{file.filename}" if source_prefix else file.filename
            
            # Check if source already exists
            source_exists = await db.source_exists(source)
            existing_chunk_count = 0
            
            if source_exists:
                existing_chunk_count = await db.get_source_chunk_count(source)
                
                if duplicate_action == "skip":
                    skipped += 1
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "skipped": True,
                        "error": f"File already exists with {existing_chunk_count} chunks. Use 'replace' or 'append' to update.",
                        "chunks_created": 0,
                        "existing_chunks": existing_chunk_count
                    })
                    continue
                elif duplicate_action == "replace":
                    # Delete existing chunks
                    deleted = await db.delete_by_source(source)
                    logger.info(f"Replacing existing document: {source} (deleted {deleted} chunks)")
            
            # Validate file
            content = await file.read()
            file_size = len(content)
            
            valid, message = document_processor.validate_file(file.filename, file_size)
            if not valid:
                failed += 1
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": message,
                    "chunks_created": 0
                })
                continue
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                # Process document
                chunks, metadata = await document_processor.process_document(tmp_path, source)
                
                if not chunks:
                    failed += 1
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "error": "No content could be extracted",
                        "chunks_created": 0
                    })
                    continue
                
                # Store chunks in database
                inserted = await db.insert_chunks_batch(chunks)
                total_chunks += inserted
                successful += 1
                
                file_time = time.time() - file_start
                result_entry = {
                    "filename": file.filename,
                    "success": True,
                    "source": source,
                    "chunks_created": inserted,
                    "file_size": file_size,
                    "processing_time": round(file_time, 2)
                }
                
                # Add info about existing chunks if appending
                if source_exists and duplicate_action == "append":
                    result_entry["action"] = "appended"
                    result_entry["existing_chunks"] = existing_chunk_count
                    result_entry["total_chunks"] = existing_chunk_count + inserted
                elif source_exists and duplicate_action == "replace":
                    result_entry["action"] = "replaced"
                    result_entry["previous_chunks"] = existing_chunk_count
                else:
                    result_entry["action"] = "new"
                
                results.append(result_entry)
                
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        
        except Exception as e:
            failed += 1
            logger.error(f"Error ingesting {file.filename}: {e}")
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e),
                "chunks_created": 0
            })
    
    total_time = time.time() - start_time
    
    message_parts = [f"Processed {len(files)} files"]
    if successful > 0:
        message_parts.append(f"{successful} successful")
    if failed > 0:
        message_parts.append(f"{failed} failed")
    if skipped > 0:
        message_parts.append(f"{skipped} skipped (already exist)")
    
    return BatchIngestResponse(
        success=successful > 0,
        message=", ".join(message_parts),
        total_files=len(files),
        successful=successful,
        failed=failed,
        results=results,
        total_chunks_created=total_chunks,
        total_processing_time=round(total_time, 2)
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """List all documents in the knowledge base."""
    try:
        sources = await db.list_sources()
        
        # Get stats per source
        documents = []
        for source in sources:
            documents.append({
                "source": source,
                "type": "document"
            })
        
        return DocumentListResponse(
            documents=documents,
            total=len(documents)
        )
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{source}")
async def delete_document(source: str):
    """Delete all chunks from a specific document source."""
    try:
        deleted = await db.delete_by_source(source)
        
        if deleted == 0:
            raise HTTPException(status_code=404, detail=f"No document found with source: {source}")
        
        return {
            "success": True,
            "message": f"Deleted {deleted} chunks from source: {source}",
            "deleted_chunks": deleted
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Document Management Endpoints (Phase 2)
# ============================================================================

@router.get("/documents/{document_id}")
async def get_document_details(document_id: int):
    """Get detailed information about a specific document."""
    try:
        from app.core.database import get_supabase_client
        client = get_supabase_client()
        
        # Get document
        doc_result = client.table('documents_registry') \
            .select('*') \
            .eq('id', document_id) \
            .execute()
        
        if not doc_result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = doc_result.data[0]
        
        # Get metadata
        meta_result = client.table('document_metadata') \
            .select('*') \
            .eq('document_id', document_id) \
            .execute()
        
        document['metadata'] = meta_result.data if meta_result.data else []
        
        return {
            "success": True,
            "document": document
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}/chunks")
async def get_document_chunks(
    document_id: int, 
    limit: int = 50, 
    offset: int = 0
):
    """Get all chunks for a specific document."""
    try:
        from app.core.database import get_supabase_client
        client = get_supabase_client()
        
        result = client.table('rag_chunks') \
            .select('id, chunk_id, text, created_at', count='exact') \
            .eq('document_id', document_id) \
            .order('id', desc=False) \
            .limit(limit) \
            .offset(offset) \
            .execute()
        
        return {
            "success": True,
            "chunks": result.data,
            "total": result.count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error getting document chunks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}")
async def delete_document_by_id(document_id: int):
    """Delete a document and all its associated chunks."""
    try:
        from app.services.cleanup import cleanup_service
        result = await cleanup_service.delete_document_and_chunks(document_id)
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to delete document"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document by ID: {e}")
        raise HTTPException(status_code=500, detail=str(e))

