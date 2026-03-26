"""
Test script for duplicate file handling in batch ingestion.
Tests skip, replace, and append functionality.
"""
import requests
import tempfile
import os

API_BASE = "http://localhost:8000"

def create_sample_file(content, prefix='test'):
    """Create a sample text file."""
    fd, path = tempfile.mkstemp(suffix='.txt', prefix=f'{prefix}_')
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    return path

def test_check_duplicates():
    """Test the duplicate checking endpoint."""
    print("\n" + "="*60)
    print("Testing Duplicate Check Endpoint")
    print("="*60)
    
    # Create and upload initial files
    print("\n1. Creating and uploading initial files...")
    file1_path = create_sample_file("Initial content for file 1", "initial_1")
    file2_path = create_sample_file("Initial content for file 2", "initial_2")
    
    try:
        # Upload first batch
        files = [
            ('files', (os.path.basename(file1_path), open(file1_path, 'rb'), 'text/plain')),
            ('files', (os.path.basename(file2_path), open(file2_path, 'rb'), 'text/plain'))
        ]
        data = {'source_prefix': 'duplicate-test'}
        
        response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        for _, (_, f, _) in files:
            f.close()
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Uploaded {result['successful']} files")
        else:
            print(f"   ❌ Upload failed: {response.status_code}")
            return
        
        # Now check for duplicates
        print("\n2. Checking for duplicates...")
        filenames = [os.path.basename(file1_path), os.path.basename(file2_path), "non_existent.txt"]
        
        response = requests.post(
            f"{API_BASE}/ingest/check-duplicates",
            json={
                "filenames": filenames,
                "source_prefix": "duplicate-test"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Check completed!")
            print(f"   Total checked: {result['total_checked']}")
            print(f"   Existing: {result['existing']}")
            print(f"\n   Details:")
            for filename, info in result['results'].items():
                status = "EXISTS" if info['exists'] else "NEW"
                chunks = f"({info['chunk_count']} chunks)" if info['exists'] else ""
                print(f"      - {filename}: {status} {chunks}")
        else:
            print(f"   ❌ Check failed: {response.status_code}")
    
    finally:
        # Cleanup
        for path in [file1_path, file2_path]:
            if os.path.exists(path):
                os.unlink(path)

def test_skip_duplicates():
    """Test skipping duplicate files."""
    print("\n" + "="*60)
    print("Testing SKIP Duplicate Action")
    print("="*60)
    
    file_path = create_sample_file("Test content for skip test", "skip_test")
    filename = os.path.basename(file_path)
    
    try:
        # First upload
        print("\n1. First upload (should succeed)...")
        with open(file_path, 'rb') as f:
            files = [('files', (filename, f, 'text/plain'))]
            data = {'source_prefix': 'skip-test', 'duplicate_action': 'skip'}
            response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ First upload successful: {result['successful']} files")
        
        # Second upload with SKIP
        print("\n2. Second upload with SKIP action (should skip)...")
        with open(file_path, 'rb') as f:
            files = [('files', (filename, f, 'text/plain'))]
            data = {'source_prefix': 'skip-test', 'duplicate_action': 'skip'}
            response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Message: {result['message']}")
            print(f"   Successful: {result['successful']}")
            print(f"   Failed: {result['failed']}")
            
            for item in result['results']:
                if item.get('skipped'):
                    print(f"   ✅ File was correctly skipped: {item['filename']}")
                    print(f"      Reason: {item['error']}")
    
    finally:
        if os.path.exists(file_path):
            os.unlink(file_path)

def test_replace_duplicates():
    """Test replacing duplicate files."""
    print("\n" + "="*60)
    print("Testing REPLACE Duplicate Action")
    print("="*60)
    
    file_path = create_sample_file("Original content for replace test", "replace_test")
    filename = os.path.basename(file_path)
    
    try:
        # First upload
        print("\n1. First upload (original content)...")
        with open(file_path, 'rb') as f:
            files = [('files', (filename, f, 'text/plain'))]
            data = {'source_prefix': 'replace-test'}
            response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            first_chunks = result['total_chunks_created']
            print(f"   ✅ First upload: {first_chunks} chunks created")
        
        # Update file content
        os.unlink(file_path)
        file_path = create_sample_file("New updated content for replace test - much longer content to create more chunks!", "replace_test")
        
        # Second upload with REPLACE
        print("\n2. Second upload with REPLACE action (should replace)...")
        with open(file_path, 'rb') as f:
            files = [('files', (filename, f, 'text/plain'))]
            data = {'source_prefix': 'replace-test', 'duplicate_action': 'replace'}
            response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Message: {result['message']}")
            print(f"   Successful: {result['successful']}")
            
            for item in result['results']:
                if item.get('action') == 'replaced':
                    print(f"   ✅ File was replaced: {item['filename']}")
                    print(f"      Previous chunks: {item.get('previous_chunks', 0)}")
                    print(f"      New chunks: {item['chunks_created']}")
    
    finally:
        if os.path.exists(file_path):
            os.unlink(file_path)

def test_append_duplicates():
    """Test appending to duplicate files."""
    print("\n" + "="*60)
    print("Testing APPEND Duplicate Action")
    print("="*60)
    
    file_path = create_sample_file("Original content for append test", "append_test")
    filename = os.path.basename(file_path)
    
    try:
        # First upload
        print("\n1. First upload (original content)...")
        with open(file_path, 'rb') as f:
            files = [('files', (filename, f, 'text/plain'))]
            data = {'source_prefix': 'append-test'}
            response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            first_chunks = result['total_chunks_created']
            print(f"   ✅ First upload: {first_chunks} chunks created")
        
        # Update file content
        os.unlink(file_path)
        file_path = create_sample_file("Additional content for append test", "append_test")
        
        # Second upload with APPEND
        print("\n2. Second upload with APPEND action (should append)...")
        with open(file_path, 'rb') as f:
            files = [('files', (filename, f, 'text/plain'))]
            data = {'source_prefix': 'append-test', 'duplicate_action': 'append'}
            response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Message: {result['message']}")
            print(f"   Successful: {result['successful']}")
            
            for item in result['results']:
                if item.get('action') == 'appended':
                    print(f"   ✅ File was appended: {item['filename']}")
                    print(f"      Existing chunks: {item.get('existing_chunks', 0)}")
                    print(f"      New chunks added: {item['chunks_created']}")
                    print(f"      Total chunks now: {item.get('total_chunks', 0)}")
    
    finally:
        if os.path.exists(file_path):
            os.unlink(file_path)

def test_mixed_batch():
    """Test batch upload with mix of new and duplicate files."""
    print("\n" + "="*60)
    print("Testing Mixed Batch (New + Duplicates)")
    print("="*60)
    
    file1 = create_sample_file("Existing file content", "existing")
    file2 = create_sample_file("New file content", "newfile")
    file3 = create_sample_file("Another new file", "newfile2")
    
    try:
        # Upload first file
        print("\n1. Pre-uploading one file...")
        with open(file1, 'rb') as f:
            files = [('files', (os.path.basename(file1), f, 'text/plain'))]
            data = {'source_prefix': 'mixed-test'}
            response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        
        if response.status_code == 200:
            print(f"   ✅ Pre-upload successful")
        
        # Now upload all three with skip
        print("\n2. Uploading batch with 1 duplicate and 2 new files (SKIP mode)...")
        files_list = []
        for path in [file1, file2, file3]:
            files_list.append(('files', (os.path.basename(path), open(path, 'rb'), 'text/plain')))
        
        data = {'source_prefix': 'mixed-test', 'duplicate_action': 'skip'}
        response = requests.post(f"{API_BASE}/ingest/batch", files=files_list, data=data)
        
        for _, (_, f, _) in files_list:
            f.close()
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n   Message: {result['message']}")
            print(f"   Total files: {result['total_files']}")
            print(f"   Successful: {result['successful']}")
            print(f"   Failed: {result['failed']}")
            print(f"\n   Per-file results:")
            
            for item in result['results']:
                if item.get('skipped'):
                    print(f"      ⊘ {item['filename']} - SKIPPED")
                elif item.get('success'):
                    print(f"      ✅ {item['filename']} - NEW ({item['chunks_created']} chunks)")
                else:
                    print(f"      ❌ {item['filename']} - ERROR")
    
    finally:
        for path in [file1, file2, file3]:
            if os.path.exists(path):
                os.unlink(path)

if __name__ == "__main__":
    print("="*60)
    print("DUPLICATE FILE HANDLING TESTS")
    print("="*60)
    print("\nMake sure the RAG API is running on http://localhost:8000")
    input("Press Enter to start tests...")
    
    try:
        # Run all tests
        test_check_duplicates()
        test_skip_duplicates()
        test_replace_duplicates()
        test_append_duplicates()
        test_mixed_batch()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED! ✅")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
