"""
Test script for batch document ingestion.
Creates sample files and tests the batch upload endpoint.
"""
import requests
import tempfile
import os

API_BASE = "http://localhost:8000"

def create_sample_files():
    """Create sample text files for testing."""
    files = []
    
    # Create 3 sample files
    for i in range(1, 4):
        content = f"""
        Sample Document {i}
        
        This is a test document for batch ingestion.
        It contains some sample content to be processed and indexed.
        
        Key information:
        - Document ID: {i}
        - Purpose: Testing batch upload
        - Content: Sample text for RAG system
        
        This document can be used to test the retrieval and query functionality
        of the Agentic RAG system.
        """
        
        fd, path = tempfile.mkstemp(suffix='.txt', prefix=f'sample_{i}_')
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        files.append(path)
    
    return files

def test_batch_upload():
    """Test batch document upload."""
    print("Creating sample files...")
    file_paths = create_sample_files()
    
    try:
        print(f"\n📤 Uploading {len(file_paths)} files...")
        
        # Prepare files for upload
        files = []
        for path in file_paths:
            filename = os.path.basename(path)
            files.append(('files', (filename, open(path, 'rb'), 'text/plain')))
        
        # Add source prefix
        data = {'source_prefix': 'test-batch'}
        
        # Upload
        response = requests.post(
            f"{API_BASE}/ingest/batch",
            files=files,
            data=data
        )
        
        # Close file handles
        for _, (_, file_obj, _) in files:
            file_obj.close()
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Batch Upload Successful!")
            print(f"   Total files: {result['total_files']}")
            print(f"   Successful: {result['successful']}")
            print(f"   Failed: {result['failed']}")
            print(f"   Total chunks: {result['total_chunks_created']}")
            print(f"   Processing time: {result['total_processing_time']}s")
            
            if result['results']:
                print("\n📋 Per-file results:")
                for item in result['results']:
                    status = "✅" if item['success'] else "❌"
                    print(f"   {status} {item['filename']}: {item.get('chunks_created', 0)} chunks")
                    if not item['success']:
                        print(f"      Error: {item.get('error', 'Unknown')}")
        else:
            print(f"\n❌ Upload failed: {response.status_code}")
            print(response.text)
    
    finally:
        # Clean up temp files
        print("\n🧹 Cleaning up...")
        for path in file_paths:
            if os.path.exists(path):
                os.unlink(path)
        print("Done!")

def test_single_upload():
    """Test single document upload for comparison."""
    print("\n\n" + "="*50)
    print("Testing Single File Upload")
    print("="*50)
    
    # Create one sample file
    content = "This is a single file upload test."
    fd, path = tempfile.mkstemp(suffix='.txt', prefix='single_test_')
    
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        
        filename = os.path.basename(path)
        
        with open(path, 'rb') as f:
            files = {'file': (filename, f, 'text/plain')}
            data = {'source': 'test-single'}
            
            response = requests.post(
                f"{API_BASE}/ingest",
                files=files,
                data=data
            )
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Single Upload Successful!")
            print(f"   Source: {result['source']}")
            print(f"   Chunks created: {result['chunks_created']}")
            print(f"   Processing time: {result['processing_time']}s")
        else:
            print(f"\n❌ Upload failed: {response.status_code}")
            print(response.text)
    
    finally:
        if os.path.exists(path):
            os.unlink(path)

if __name__ == "__main__":
    print("="*50)
    print("Testing Batch Document Ingestion")
    print("="*50)
    
    try:
        # Test batch upload
        test_batch_upload()
        
        # Test single upload for comparison
        test_single_upload()
        
        print("\n" + "="*50)
        print("All tests completed!")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
