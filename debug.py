"""
Unified Debug Tool for RAG System
Usage:
    python debug.py query "Your question here"    # Single query with detailed output
    python debug.py interactive                     # Interactive multi-query session
    python debug.py ollama                          # Test Ollama connection directly
"""
import asyncio
import logging
import sys
import ollama
from app.services.agent import create_agent
from app.core.config import settings

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 100)
    print(title.center(100))
    print("=" * 100)

def print_section(title):
    """Print a formatted section."""
    print("\n" + "-" * 100)
    print(title)
    print("-" * 100)

async def test_single_query(query: str):
    """Test a single query with detailed debug output."""
    print_header("RAG SYSTEM DEBUG TEST - SINGLE QUERY")
    print(f"Min confidence threshold: {settings.min_confidence_threshold}")
    print(f"Max iterations: {settings.max_agent_iterations}")
    print(f"Ollama model: {settings.ollama_llm_model}")
    print(f"Enable verification: {settings.enable_verification}")
    print("=" * 100)
    print(f"\nQUERY: {query}")
    print("=" * 100 + "\n")
    
    try:
        # Create agent instance
        agent = create_agent()
        
        # Execute query
        print("Starting query processing...\n")
        state = await agent.query(query)
        
        print_header("FINAL RESULT")
        print_section("Answer")
        print(state.final_answer if state.final_answer else "[NO ANSWER GENERATED]")
        
        print_section("Metadata")
        print(f"Confidence: {state.confidence}")
        print(f"Iterations: {state.iteration}")
        print(f"Retrieved chunks: {len(state.retrieved_docs)}")
        print(f"Verification results: {len(state.verification_results)}")
        
        if state.verification_results:
            last_verification = state.verification_results[-1]
            print(f"\nLast Verification:")
            print(f"  - Verified: {last_verification.get('verified', False)}")
            print(f"  - Confidence: {last_verification.get('confidence', 'N/A')}")
            print(f"  - Grounding Score: {last_verification.get('grounding_score', 'N/A')}")
            if last_verification.get('issues'):
                print(f"  - Issues: {', '.join(last_verification['issues'])}")
        
        if state.sources:
            print(f"\nSources ({len(state.sources)} total):")
            for i, source in enumerate(state.sources[:5], 1):
                print(f"  {i}. {source}")
            if len(state.sources) > 5:
                print(f"  ... and {len(state.sources) - 5} more")
        
        print(f"\nReasoning Trace ({len(state.reasoning)} steps):")
        for i, step in enumerate(state.reasoning, 1):
            content_preview = step[:80] + "..." if len(step) > 80 else step
            print(f"  {i}. {content_preview}")
        
        print("=" * 100 + "\n")
        
        return state
    except Exception as e:
        print_header("ERROR")
        print(f"{e}")
        import traceback
        traceback.print_exc()
        print("=" * 100 + "\n")

async def interactive_mode():
    """Interactive multi-query testing mode."""
    print_header("RAG SYSTEM DEBUG - INTERACTIVE MODE")
    print(f"Min confidence threshold: {settings.min_confidence_threshold}")
    print(f"Max iterations: {settings.max_agent_iterations}")
    print(f"Ollama model: {settings.ollama_llm_model}")
    print(f"Enable verification: {settings.enable_verification}")
    print("=" * 100)
    print("\nType your queries (or 'quit'/'exit' to stop)\n")
    
    while True:
        try:
            query = input("\n🔍 Query: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            await test_single_query(query)
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

def test_ollama():
    """Test Ollama directly without the RAG system."""
    print_header("DIRECT OLLAMA TEST")
    
    model = settings.ollama_llm_model or "llama3.1:8b"
    host = settings.ollama_host or "http://localhost:11434"
    
    print(f"Connecting to: {host}")
    print(f"Model: {model}\n")
    
    try:
        client = ollama.Client(host=host)
        
        # Test 1: Simple greeting
        print_section("TEST 1: Simple Greeting")
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": "Say hello in one sentence."}],
            options={"temperature": 0.7, "num_predict": 50}
        )
        print(f"Response: {response['message']['content']}")
        print(f"Length: {len(response['message']['content'])}")
        
        if not response['message']['content']:
            print("⚠️  WARNING: Empty response!")
        else:
            print("✅ Response received successfully")
        
        # Test 2: Verification-style prompt
        print_section("TEST 2: Verification Prompt")
        
        verification_prompt = """You are a verification agent. Check if the answer is grounded in the provided context.

User Query: What is Deep Q Learning?

Proposed Answer: Deep Q Learning is a reinforcement learning algorithm.

Context:
Deep Q Learning (DQL) is a model-free reinforcement learning algorithm that uses neural networks.

Verify:
1. Is every claim in the answer supported by the context?
2. Are there any fabricated or unsupported statements?
3. What is your confidence level (0.0-1.0)?

Respond with: verified: [true/false], confidence: [0.0-1.0]"""
        
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": verification_prompt}],
            options={"temperature": 0.3, "num_predict": 200}
        )
        print(f"Response: {response['message']['content']}")
        print(f"Length: {len(response['message']['content'])}")
        
        if not response['message']['content']:
            print("⚠️  WARNING: Empty response!")
        else:
            print("✅ Response received successfully")
        
        # Test 3: Check thinking field (for models like qwen3.5)
        print_section("TEST 3: Response Structure Check")
        if 'thinking' in response['message']:
            print(f"🧠 Thinking field exists: {len(response['message'].get('thinking', ''))} chars")
            if response['message'].get('thinking'):
                print(f"Thinking content: {response['message']['thinking'][:200]}...")
        else:
            print("ℹ️  No thinking field (normal for most models)")
        
        print(f"📝 Content field: {len(response['message']['content'])} chars")
        print(f"✅ Done reason: {response.get('done_reason', 'N/A')}")
        
        print_section("CONNECTION TEST COMPLETE")
        print("✅ Ollama is working correctly!")
        
    except Exception as e:
        print_header("ERROR")
        print(f"❌ Failed to connect to Ollama: {e}")
        print("\nTroubleshooting:")
        print("1. Check if Ollama is running: ollama list")
        print(f"2. Verify the model exists: ollama run {model} 'test'")
        print("3. Check Ollama service: curl http://localhost:11434")
        import traceback
        traceback.print_exc()

def show_help():
    """Show usage information."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        RAG System Debug Tool                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

USAGE:
    python debug.py query "Your question here"    # Single query with detailed output
    python debug.py interactive                     # Interactive multi-query session
    python debug.py ollama                          # Test Ollama connection directly
    python debug.py help                            # Show this help message

EXAMPLES:
    # Test a single query
    python debug.py query "What is Deep Q Learning?"
    
    # Interactive mode for multiple queries
    python debug.py interactive
    
    # Test if Ollama is working
    python debug.py ollama

DEBUGGING TIPS:
    • Look for "DEBUG:" markers in output for troubleshooting
    • Check confidence scores - should be > 0.5 for good answers
    • Review reasoning trace to understand agent decisions
    • Use "ollama" mode to isolate Ollama connection issues

For more information, see README.MD - Debugging section.
    """)

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "query":
        if len(sys.argv) < 3:
            print("❌ Error: Query text required")
            print("Usage: python debug.py query \"Your question here\"")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        asyncio.run(test_single_query(query))
    
    elif command == "interactive":
        asyncio.run(interactive_mode())
    
    elif command == "ollama":
        test_ollama()
    
    elif command in ["help", "-h", "--help"]:
        show_help()
    
    else:
        print(f"❌ Unknown command: {command}")
        show_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
