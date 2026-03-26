"""
Seed sample documents into the RAG system.
"""
import asyncio
from pathlib import Path
from app.services.document_processor import document_processor
from app.core.database import db

async def seed_sample_documents():
    print("🌱 Seeding sample documents into RAG system")
    print("=" * 60)
    
    # Sample text documents to create
    samples = {
        "sample_faq.txt": """
Frequently Asked Questions

Q: What is the return policy?
A: We offer a 30-day money-back guarantee on all products. Items must be in original condition.

Q: How long does shipping take?
A: Standard shipping takes 3-5 business days. Express shipping is available for 1-2 day delivery.

Q: Do you ship internationally?
A: Yes, we ship to over 50 countries worldwide. International shipping takes 7-14 business days.

Q: How can I track my order?
A: You'll receive a tracking number via email once your order ships. Use this on our website to track your package.
""",
        "sample_about.txt": """
About Our Company

We are a leading provider of innovative solutions since 2010. Our mission is to deliver high-quality products
that make a difference in people's lives.

Our Values:
- Customer satisfaction is our top priority
- Innovation drives everything we do
- Sustainability and environmental responsibility
- Transparent and ethical business practices

Team:
Our team consists of 200+ dedicated professionals across multiple countries, working together to serve
our global customer base of over 1 million satisfied customers.
""",
        "sample_products.txt": """
Product Catalog

Premium Widget
- Price: .99
- Features: Durable, lightweight, eco-friendly
- Warranty: 2 years
- Colors: Red, Blue, Green, Black

Deluxe Widget
- Price: .99  
- Features: All Premium features plus advanced controls
- Warranty: 3 years
- Colors: Silver, Gold, Platinum

Enterprise Widget  
- Price: Contact for quote
- Features: Custom configuration, dedicated support
- Warranty: 5 years
- Colors: Custom colors available
"""
    }
    
    # Create temp directory for samples
    temp_dir = Path("temp_samples")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        total_chunks = 0
        
        for filename, content in samples.items():
            file_path = temp_dir / filename
            file_path.write_text(content, encoding='utf-8')
            
            print(f"\n📄 Processing: {filename}")
            
            try:
                # Process document
                chunks, metadata = await document_processor.process_document(
                    str(file_path), 
                    filename
                )
                
                # Insert into database
                inserted = await db.insert_chunks_batch(chunks)
                total_chunks += inserted
                
                print(f"   ✓ Created {inserted} chunks")
                
            except Exception as e:
                print(f"   ✗ Error: {e}")
        
        print("\n" + "=" * 60)
        print(f"✅ Seeding complete! Total chunks created: {total_chunks}")
        print("\nYou can now query the system with questions like:")
        print("  • What is the return policy?")
        print("  • Tell me about the company")
        print("  • What products are available?")
        
    finally:
        # Cleanup temp files
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    asyncio.run(seed_sample_documents())
