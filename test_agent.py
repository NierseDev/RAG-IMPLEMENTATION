"""
Quick test script for the Agentic RAG system.
"""
import asyncio
import sys
from app.services.agent import create_agent

async def test_agent():
    print("🤖 Testing Agentic RAG System")
    print("=" * 60)
    
    # Create agent
    agent = create_agent()
    
    # Test query
    test_query = "What information is available in the knowledge base?"
    print(f"\n📝 Query: {test_query}\n")
    
    try:
        # Execute query
        state = await agent.query(test_query)
        
        print("\n" + "=" * 60)
        print("📊 RESULTS")
        print("=" * 60)
        print(f"Answer: {state.final_answer}")
        print(f"\nIterations: {state.iteration}")
        print(f"Retrieved Chunks: {len(state.retrieved_docs)}")
        print(f"Confidence: {state.confidence:.2f}" if state.confidence else "Confidence: N/A")
        
        print("\n🧠 REASONING TRACE:")
        for step in state.reasoning:
            print(f"  • {step}")
        
        print("\n📚 SOURCES:")
        for source in state.sources:
            print(f"  • {source}")
        
        print("\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_agent())
