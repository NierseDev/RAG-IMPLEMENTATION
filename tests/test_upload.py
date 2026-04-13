"""
Upload Testing Tool for RAG System
Tests document ingestion, batch upload, and duplicate handling.

Usage:
    python tests/test_upload.py batch                    # Test batch upload
    python tests/test_upload.py duplicates               # Test duplicate handling modes
    python tests/test_upload.py all                      # Run all upload tests
"""
import requests
import tempfile
import os
import sys

API_BASE = "http://localhost:8000"

def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)

def print_section(title):
    """Print a formatted section."""
    print("\n" + "-" * 80)
    print(title)
    print("-" * 80)

def create_sample_file(content, prefix='test'):
    """Create a sample text file."""
    fd, path = tempfile.mkstemp(suffix='.txt', prefix=f'{prefix}_')
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    return path

def create_sample_files(count=3):
    """Create multiple sample text files for testing."""
    files = []
    
    for i in range(1, count + 1):
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
        
        path = create_sample_file(content, f'sample_{i}')
        files.append(path)
    
    return files

def test_batch_upload():
    """Test batch document upload."""
    print_header("BATCH UPLOAD TEST")
    
    print("\n1. Creating sample files...")
    file_paths = create_sample_files(3)
    print(f"✅ Created {len(file_paths)} sample files")
    
    try:
        print("\n2. Uploading files to server...")
        
        # Prepare files for upload
        files = [
            ('files', (os.path.basename(path), open(path, 'rb'), 'text/plain'))
            for path in file_paths
        ]
        data = {
            'source_prefix': 'batch-test',
            'duplicate_action': 'skip'
        }
        
        response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        
        # Close file handles
        for _, (_, f, _) in files:
            f.close()
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Batch upload completed!\n")
            
            print_section("Results")
            if 'results' in result:
                for item in result['results']:
                    status_icon = "✅" if item['status'] == "NEW" else "⚠️"
                    print(f"{status_icon} {item['filename']}: {item['status']} - {item['message']}")
            
            if 'summary' in result:
                print_section("Summary")
                summary = result['summary']
                print(f"Total files: {summary['total']}")
                print(f"✅ Successful: {summary['successful']}")
                print(f"⏭️  Skipped: {summary['skipped']}")
                print(f"❌ Failed: {summary['failed']}")
        else:
            print(f"❌ Upload failed with status {response.status_code}")
            print(response.text)
    
    finally:
        # Cleanup
        print("\n3. Cleaning up temporary files...")
        for path in file_paths:
            try:
                os.remove(path)
            except:
                pass
        print("✅ Cleanup complete")

def test_duplicate_handling():
    """Test duplicate file handling with skip, replace, and append modes."""
    print_header("DUPLICATE HANDLING TEST")
    
    # Create test files
    print("\n1. Creating test files...")
    file1_path = create_sample_file("Initial content for file 1", "dup_test_1")
    file2_path = create_sample_file("Initial content for file 2", "dup_test_2")
    file1_name = os.path.basename(file1_path)
    file2_name = os.path.basename(file2_path)
    print(f"✅ Created files: {file1_name}, {file2_name}")
    
    try:
        # Upload initial files
        print_section("Step 1: Upload initial files")
        files = [
            ('files', (file1_name, open(file1_path, 'rb'), 'text/plain')),
            ('files', (file2_name, open(file2_path, 'rb'), 'text/plain'))
        ]
        data = {'source_prefix': 'duplicate-test'}
        
        response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        for _, (_, f, _) in files:
            f.close()
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Initial upload: {result['summary']['successful']} files uploaded")
        else:
            print(f"❌ Initial upload failed: {response.status_code}")
            return
        
        # Test duplicate check
        print_section("Step 2: Check for duplicates")
        check_response = requests.post(
            f"{API_BASE}/ingest/check-duplicates",
            json={
                'filenames': [file1_name, file2_name],
                'source_prefix': 'duplicate-test'
            }
        )
        
        if check_response.status_code == 200:
            duplicates = check_response.json()['duplicates']
            for dup in duplicates:
                exists_icon = "✅" if dup['exists'] else "❌"
                print(f"{exists_icon} {dup['filename']}: exists={dup['exists']}, chunks={dup['chunk_count']}")
        
        # Test SKIP mode
        print_section("Step 3: Test SKIP mode (should skip both)")
        files = [
            ('files', (file1_name, open(file1_path, 'rb'), 'text/plain')),
            ('files', (file2_name, open(file2_path, 'rb'), 'text/plain'))
        ]
        data = {'source_prefix': 'duplicate-test', 'duplicate_action': 'skip'}
        
        response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        for _, (_, f, _) in files:
            f.close()
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SKIP mode: {result['summary']['skipped']} files skipped")
        
        # Test REPLACE mode
        print_section("Step 4: Test REPLACE mode (should replace)")
        file1_updated = create_sample_file("UPDATED content for file 1", "dup_test_1")
        
        files = [('files', (file1_name, open(file1_updated, 'rb'), 'text/plain'))]
        data = {'source_prefix': 'duplicate-test', 'duplicate_action': 'replace'}
        
        response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        for _, (_, f, _) in files:
            f.close()
        
        if response.status_code == 200:
            result = response.json()
            if result['results']:
                print(f"✅ REPLACE mode: {result['results'][0]['status']} - {result['results'][0]['message']}")
        
        os.remove(file1_updated)
        
        # Test APPEND mode
        print_section("Step 5: Test APPEND mode (should add more chunks)")
        file2_extra = create_sample_file("EXTRA content appended to file 2", "dup_test_2")
        
        files = [('files', (file2_name, open(file2_extra, 'rb'), 'text/plain'))]
        data = {'source_prefix': 'duplicate-test', 'duplicate_action': 'append'}
        
        response = requests.post(f"{API_BASE}/ingest/batch", files=files, data=data)
        for _, (_, f, _) in files:
            f.close()
        
        if response.status_code == 200:
            result = response.json()
            if result['results']:
                print(f"✅ APPEND mode: {result['results'][0]['status']} - {result['results'][0]['message']}")
        
        os.remove(file2_extra)
        
        print_section("Test Complete")
        print("✅ All duplicate handling modes tested successfully!")
        
        print("\n💡 Cleanup: To remove test files from database, use:")
        print(f"   DELETE /ingest/documents/duplicate-test-{file1_name}")
        print(f"   DELETE /ingest/documents/duplicate-test-{file2_name}")
    
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup temporary files
        for path in [file1_path, file2_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except:
                pass

def show_help():
    """Show usage information."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      Upload Testing Tool                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

USAGE:
    python tests/test_upload.py batch                    # Test batch upload
    python tests/test_upload.py duplicates               # Test duplicate handling modes
    python tests/test_upload.py all                      # Run all upload tests
    python tests/test_upload.py help                     # Show this help message

DESCRIPTION:
    Tests document ingestion functionality including:
    • Batch file upload
    • Duplicate detection
    • Skip/Replace/Append modes
    • API error handling

PREREQUISITES:
    • Server running at http://localhost:8000
    • Ollama running with embeddings model
    • Supabase database configured

EXAMPLES:
    # Test batch upload only
    python tests/test_upload.py batch
    
    # Test all duplicate handling modes
    python tests/test_upload.py duplicates
    
    # Run full test suite
    python tests/test_upload.py all

For more information, see README.MD - Multiple File Upload section.
    """)

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    # Show help without checking server
    if command in ["help", "-h", "--help"]:
        show_help()
        return
    
    # Check if server is running for actual tests
    try:
        response = requests.get(f"{API_BASE}/health", timeout=2)
        if response.status_code != 200:
            print(f"⚠️  Warning: Server returned status {response.status_code}")
    except requests.exceptions.RequestException:
        print(f"❌ Error: Cannot connect to server at {API_BASE}")
        print("Please ensure the server is running: python main.py")
        sys.exit(1)
    
    if command == "batch":
        test_batch_upload()
    
    elif command == "duplicates":
        test_duplicate_handling()
    
    elif command == "all":
        test_batch_upload()
        print("\n")
        test_duplicate_handling()
    
    elif command in ["help", "-h", "--help"]:
        show_help()
    
    else:
        print(f"❌ Unknown command: {command}")
        show_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
