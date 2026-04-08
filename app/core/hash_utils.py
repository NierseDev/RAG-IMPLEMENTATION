"""
File hashing utility for document deduplication.
Uses SHA-256 with streaming support for large files.
"""
import hashlib
from pathlib import Path
from typing import Union, BinaryIO
import logging

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8192  # 8KB chunks for streaming


def compute_file_hash(file_path: Union[str, Path]) -> str:
    """
    Compute SHA-256 hash of a file using streaming to handle large files.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Hexadecimal hash string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file can't be read
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    sha256_hash = hashlib.sha256()
    
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                sha256_hash.update(chunk)
        
        hash_value = sha256_hash.hexdigest()
        logger.debug(f"Computed hash for {file_path.name}: {hash_value[:16]}...")
        return hash_value
        
    except IOError as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        raise


def compute_bytes_hash(file_bytes: bytes) -> str:
    """
    Compute SHA-256 hash of raw bytes (for in-memory files).
    
    Args:
        file_bytes: Raw file bytes
        
    Returns:
        Hexadecimal hash string
    """
    sha256_hash = hashlib.sha256()
    sha256_hash.update(file_bytes)
    hash_value = sha256_hash.hexdigest()
    logger.debug(f"Computed hash for bytes: {hash_value[:16]}...")
    return hash_value


def compute_stream_hash(file_stream: BinaryIO) -> str:
    """
    Compute SHA-256 hash of a file stream (for uploaded files).
    
    Args:
        file_stream: File-like object (e.g., FastAPI UploadFile.file)
        
    Returns:
        Hexadecimal hash string
    """
    sha256_hash = hashlib.sha256()
    
    # Save current position and reset to beginning
    original_position = file_stream.tell()
    file_stream.seek(0)
    
    try:
        for chunk in iter(lambda: file_stream.read(CHUNK_SIZE), b""):
            sha256_hash.update(chunk)
        
        hash_value = sha256_hash.hexdigest()
        logger.debug(f"Computed hash for stream: {hash_value[:16]}...")
        return hash_value
        
    finally:
        # Reset to original position
        file_stream.seek(original_position)


def verify_file_hash(file_path: Union[str, Path], expected_hash: str) -> bool:
    """
    Verify that a file's hash matches the expected hash.
    
    Args:
        file_path: Path to the file
        expected_hash: Expected SHA-256 hash
        
    Returns:
        True if hash matches, False otherwise
    """
    try:
        actual_hash = compute_file_hash(file_path)
        matches = actual_hash == expected_hash
        
        if matches:
            logger.info(f"Hash verification passed for {file_path}")
        else:
            logger.warning(f"Hash mismatch for {file_path}: expected {expected_hash[:16]}..., got {actual_hash[:16]}...")
            
        return matches
        
    except Exception as e:
        logger.error(f"Hash verification failed for {file_path}: {e}")
        return False
