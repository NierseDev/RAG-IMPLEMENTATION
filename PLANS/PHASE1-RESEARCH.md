# Phase 1: Model Research & Optimization for Agentic RAG

**Machine Specs**: AMD Ryzen 5 8600G (6C/12T) + Radeon 760M iGPU (2GB VRAM)  
**Current Models**: qwen3.5:4b (LLM), mxbai-embed-large (embeddings)

---

## 🎯 Research Goals

1. **CPU-Optimized (PRIORITY)**: Find fastest models for CPU-only execution
2. **GPU-Optimized**: Leverage Radeon 760M for improved performance  
3. **Cloud Budget**: Low-cost cloud alternatives (<$0.20 per 1M tokens)
4. **Cloud Balanced**: Production-grade performance at reasonable cost

---

## 🖥️ LOCAL MODELS RESEARCH

### A. CPU-Optimized Models (AMD Ryzen 5 8600G)

**Current**: qwen3.5:4b (3.4GB, 256k context)

#### Top Recommendations for RAG on CPU:

1. **Qwen3.5:4b** ✅ (Current - KEEP)
   - **Size**: 3.4GB
   - **Context**: 256k tokens
   - **Speed**: ~15-20 tokens/sec on Ryzen 5
   - **Quality**: Excellent instruction following, strong RAG performance
   - **Why**: Best balance of speed + quality for 6-core CPU
   - **RAM**: ~4GB
   
2. **Llama 3.2:3b** ✅ (Already installed)
   - **Size**: 2GB  
   - **Context**: 128k tokens
   - **Speed**: ~20-25 tokens/sec
   - **Quality**: Good for simpler queries, faster iteration
   - **Why**: Fallback for speed-critical scenarios
   - **RAM**: ~3GB

3. **Phi-4:14b-q4_K_M** (Consider testing)
   - **Size**: ~8GB quantized
   - **Context**: 16k tokens (limitation!)
   - **Speed**: ~8-12 tokens/sec
   - **Quality**: Microsoft's best reasoning model
   - **Why**: Superior reasoning but slower, context limit is a concern
   - **RAM**: ~10GB
   - **Command**: `ollama pull phi4:14b-q4_k_m`

4. **Gemma 2:9b-q4** (Alternative)
   - **Size**: ~6GB
   - **Context**: 8k tokens (too small for complex RAG!)
   - **Speed**: ~10-15 tokens/sec
   - **Quality**: Strong factual accuracy
   - **Why**: Good quality but context window too restrictive
   - **Command**: `ollama pull gemma2:9b-q4`

#### Embedding Models:

1. **mxbai-embed-large** ✅ (Current - KEEP)
   - **Size**: 669MB
   - **Dimensions**: 1024
   - **Context**: 512 tokens
   - **Quality**: Best open-source embeddings
   - **Speed**: ~100 docs/sec on CPU

2. **nomic-embed-text** (Alternative)
   - **Size**: ~550MB
   - **Dimensions**: 768
   - **Context**: 8192 tokens (HUGE advantage!)
   - **Quality**: Slightly lower than mxbai but faster
   - **Command**: `ollama pull nomic-embed-text`
   - **Why**: Consider if you need longer chunk sizes

---

### B. GPU-Optimized Models (Radeon 760M - 2GB VRAM)

**Challenge**: 2GB VRAM is limited. Can only run small quantized models.

#### Viable Options:

1. **Qwen3.5:4b** (Already works on iGPU)
   - Can offload to GPU for ~25-30% speedup
   - VRAM: ~1.5GB
   - **Ollama env**: `OLLAMA_NUM_GPU=1`

2. **Llama 3.2:3b** 
   - Better GPU utilization due to smaller size
   - VRAM: ~1.2GB
   - ~40% faster on GPU vs CPU

3. **Phi-3.5-mini:3.8b** (New recommendation)
   - **Size**: ~2.5GB
   - **Context**: 128k
   - **Speed**: Optimized for smaller GPUs
   - **Quality**: Excellent reasoning for size
   - **Command**: `ollama pull phi3.5:3.8b`

**GPU Acceleration Setup**:
```bash
# Enable GPU in Ollama (Windows)
$env:OLLAMA_NUM_GPU=1
ollama serve
```

**Recommendation**: Due to 2GB VRAM limitation, GPU acceleration provides marginal benefit (~20-30% speedup). **Stick with CPU** unless you need that extra speed.

---

## ☁️ CLOUD MODELS RESEARCH

### C. Budget Cloud Options (<$0.20 per 1M tokens)

1. **Groq** (FASTEST) ⚡
   - **Model**: llama-3.3-70b-versatile
   - **Cost**: $0.59/$0.79 per 1M tokens (input/output)
   - **Speed**: 300+ tokens/sec (!)
   - **Context**: 128k
   - **Why**: Unbeatable speed for RAG iteration loops
   - **API**: Compatible with OpenAI SDK
   - **Rate Limits**: Free tier: 30 req/min

2. **OpenRouter** (FLEXIBLE)
   - **Models**: Multiple providers in one API
   - **Cost**: Starting at $0.10 per 1M tokens
   - **Options**: Meta Llama 3.1 70B, Mistral 7B, etc.
   - **Why**: Access to many models, fallback options
   - **API**: OpenAI-compatible

3. **Together AI** (GOOD VALUE)
   - **Model**: Llama-3.3-70B-Instruct
   - **Cost**: $0.18/$0.18 per 1M tokens
   - **Speed**: ~50 tokens/sec
   - **Context**: 128k
   - **Why**: Cheap, reliable, good for production

4. **Deepseek** (ULTRA CHEAP)
   - **Model**: deepseek-chat
   - **Cost**: $0.14/$0.28 per 1M tokens  
   - **Speed**: ~30 tokens/sec
   - **Context**: 64k
   - **Why**: Cheapest option, decent quality

### D. Balanced Cloud Options (Production Grade)

1. **Anthropic Claude 3.5 Sonnet** (BEST QUALITY)
   - **Cost**: $3/$15 per 1M tokens
   - **Speed**: ~30 tokens/sec
   - **Context**: 200k
   - **Why**: Best reasoning, citation accuracy, low hallucination
   - **Best for**: Critical applications where accuracy matters

2. **OpenAI GPT-4o-mini** (FAST + CHEAP)
   - **Cost**: $0.15/$0.60 per 1M tokens
   - **Speed**: ~80 tokens/sec
   - **Context**: 128k
   - **Why**: Great balance, multimodal support
   - **Best for**: General purpose RAG

3. **Google Gemini 2.0 Flash** (FAST + CHEAP)
   - **Cost**: $0.075/$0.30 per 1M tokens (CHEAPEST good model!)
   - **Speed**: ~100 tokens/sec
   - **Context**: 1M tokens (!!)
   - **Why**: Massive context window, very fast, cheap
   - **Best for**: Long document processing

4. **OpenAI GPT-4o** (BALANCED PREMIUM)
   - **Cost**: $2.50/$10 per 1M tokens
   - **Speed**: ~50 tokens/sec
   - **Context**: 128k
   - **Why**: Best overall OpenAI model, consistent quality

---

## 📊 RECOMMENDATIONS BY USE CASE

### Local Development & Testing
- **LLM**: qwen3.5:4b (current) ✅
- **Embeddings**: mxbai-embed-large (current) ✅
- **Why**: Free, fast enough, no API costs

### Local Production (Self-Hosted)
- **LLM**: qwen3.5:4b or phi-4:14b-q4 (if RAM allows)
- **Embeddings**: mxbai-embed-large
- **Why**: Best quality without cloud costs

### Cloud Budget (<$10/month for moderate use)
- **LLM**: Groq (llama-3.3-70b) or Together AI
- **Embeddings**: Keep local (mxbai-embed-large)
- **Why**: Free/cheap inference, only pay for LLM calls

### Cloud Production (Quality Matters)
- **LLM**: Gemini 2.0 Flash (best value) or Claude 3.5 Sonnet (best quality)
- **Embeddings**: OpenAI text-embedding-3-small ($0.02/1M tokens)
- **Why**: Professional grade, reliable SLA

---

## 🚀 NEXT STEPS

1. ✅ Keep current models (qwen3.5:4b + mxbai-embed-large) - already optimal
2. Test phi-4:14b-q4 for comparison (optional)
3. Implement cloud provider config (Groq, OpenAI, Anthropic, Gemini)
4. Add provider switching in environment variables
5. Benchmark and compare latency/quality

---

## 📝 Implementation Notes

**What to update**:
1. `app/core/config.py` - Add cloud provider settings
2. `app/services/llm.py` - Abstract LLM calls to support multiple providers
3. `app/services/embedding.py` - Support cloud embeddings (optional)
4. `.env` - Add API keys for cloud providers
5. `requirements.txt` - Add cloud SDK dependencies (openai, anthropic, google-generativeai)

**Testing Strategy**:
- Benchmark on sample queries (latency, quality, cost)
- Test agentic loop with each provider
- Measure retrieval quality with different embeddings
- Document findings in benchmark results
