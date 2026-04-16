"""
Verification service for hallucination detection and answer validation.
"""
from typing import Any, Dict, List, Tuple
from app.services.llm import llm_service, LLMBudgetExceededError, LLMRateLimitError
from app.models.entities import RetrievalResult
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
from app.services.retrieval import retrieval_service
import logging
import re

logger = logging.getLogger(__name__)


class VerificationService:
    """Service for verifying answers and detecting hallucinations."""

    STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
        "how", "if", "in", "is", "it", "its", "of", "on", "or", "that", "the", "their",
        "there", "these", "this", "to", "was", "were", "what", "when", "where", "which",
        "who", "why", "with", "will", "would", "can", "could", "should", "may", "might",
        "about", "into", "over", "under", "than", "then", "also", "more", "most"
    }
    
    async def verify_answer(
        self,
        query: str,
        answer: str,
        retrieved_docs: List[RetrievalResult]
    ) -> Dict:
        """
        Verify an answer against retrieved context.
        Returns: {verified: bool, confidence: float, issues: List[str]}
        """
        try:
            # Format context with token limits
            context = self._format_context(retrieved_docs)
            
            # Ensure context fits within limits
            context_tokens = estimate_tokens(context)
            max_context_tokens = settings.max_context_tokens // 4
            
            if context_tokens > max_context_tokens:
                logger.warning(f"Verification context ({context_tokens} tokens) exceeds limit. Truncating.")
                context = truncate_to_token_limit(context, max_context_tokens)
            
            # Use LLM to verify
            verification_prompt = llm_service.create_verify_prompt(query, answer, context)
            verification_result = await llm_service.generate(
                verification_prompt,
                temperature=0.3,  # Low temperature for consistency
                max_tokens=llm_service.get_phase_max_tokens("verify", 300),
                phase="verify"
            )
            
            # DEBUG: Log raw LLM response
            logger.info("=" * 80)
            logger.info("DEBUG: Raw LLM Verification Response:")
            logger.info("-" * 80)
            logger.info(verification_result)
            logger.info("=" * 80)
            
            # Parse verification result
            parsed = self._parse_verification(verification_result)
            
            # DEBUG: Log parsed result
            logger.info(f"DEBUG: Parsed verification - verified={parsed['verified']}, confidence={parsed['confidence']}, issues={parsed['issues']}")
            
            # Additional checks
            support_analysis = self._analyze_answer_support(answer, retrieved_docs)
            grounding_score = support_analysis["supported_ratio"]
            retrieval_strength = self._calculate_retrieval_strength(retrieved_docs)
            evidence_score = max(grounding_score, retrieval_strength)
            parsed['grounding_score'] = grounding_score
            parsed['retrieval_strength'] = retrieval_strength
            parsed['evidence_score'] = evidence_score
            parsed['claim_support_score'] = support_analysis["supported_ratio"]
            parsed['unsupported_claims'] = support_analysis["unsupported_claims"]
            logger.info(
                f"DEBUG: Grounding score={grounding_score:.2f}, "
                f"retrieval strength={retrieval_strength:.2f}, evidence={evidence_score:.2f}"
            )

            if support_analysis["unsupported_claims"]:
                parsed['issues'].extend(support_analysis["unsupported_claims"])

            if not support_analysis["unsupported_claims"] and support_analysis["supported_ratio"] >= 0.55:
                parsed['verified'] = True
            elif support_analysis["unsupported_claims"]:
                parsed['verified'] = False

            # Rebalance confidence: evidence can lift conservative verification,
            # but weak evidence still keeps the answer conservative.
            original_confidence = parsed['confidence']
            blended_confidence = (parsed['confidence'] * 0.3) + (evidence_score * 0.4) + (support_analysis["supported_ratio"] * 0.3)
            if evidence_score >= 0.65:
                parsed['confidence'] = max(blended_confidence, evidence_score * 0.95)
            else:
                parsed['confidence'] = blended_confidence

            if evidence_score < 0.35:
                parsed['confidence'] = min(parsed['confidence'], 0.5)
                parsed['issues'].append(f"Low evidence score: {evidence_score:.2f}")

            if support_analysis["unsupported_claims"] and parsed['confidence'] > 0.7:
                parsed['confidence'] = 0.7

            if parsed['confidence'] != original_confidence:
                logger.warning(
                    f"DEBUG: Confidence adjusted from {original_confidence:.2f} "
                    f"to {parsed['confidence']:.2f}"
                )

            logger.info(f"Verification: {parsed['verified']}, confidence: {parsed['confidence']:.2f}")
            return parsed
            
        except (LLMBudgetExceededError, LLMRateLimitError) as e:
            logger.warning(f"Verification skipped due to LLM budget/rate limit: {e}")
            return {
                'verified': False,
                'confidence': 0.5,
                'issues': [f"Verification skipped: {str(e)}"],
                'grounding_score': 0.0
            }
        except Exception as e:
            logger.error(f"Error in verification: {e}")
            return {
                'verified': False,
                'confidence': 0.0,
                'issues': [f"Verification error: {str(e)}"],
                'grounding_score': 0.0
            }
    
    def _check_grounding(self, answer: str, retrieved_docs: List[RetrievalResult]) -> float:
        """
        Check how well the answer is grounded in the retrieved documents.
        Returns a score between 0.0 and 1.0.
        """
        return self._analyze_answer_support(answer, retrieved_docs)["supported_ratio"]

    def _analyze_answer_support(
        self,
        answer: str,
        retrieved_docs: List[RetrievalResult]
    ) -> Dict[str, Any]:
        """Estimate which answer claims are supported by the retrieved context."""
        if not answer or not retrieved_docs:
            return {
                "supported_ratio": 0.0,
                "supported_claims": [],
                "unsupported_claims": ["No grounded evidence available"]
            }

        context_text = " ".join(doc.text for doc in retrieved_docs).lower()
        context_tokens_list = self._content_tokens(context_text)
        context_tokens = set(context_tokens_list)
        context_bigrams = self._build_bigrams(context_tokens_list)

        supported_claims = []
        unsupported_claims = []
        sentences = self._split_sentences(answer)

        for sentence in sentences:
            supported, reason = self._sentence_supported(sentence, context_text, context_tokens, context_bigrams)
            if supported:
                supported_claims.append(sentence)
            else:
                unsupported_claims.append(reason)

        total_claims = len(sentences) or 1
        supported_ratio = len(supported_claims) / total_claims
        return {
            "supported_ratio": supported_ratio,
            "supported_claims": supported_claims,
            "unsupported_claims": unsupported_claims
        }

    def _calculate_retrieval_strength(self, retrieved_docs: List[RetrievalResult]) -> float:
        """
        Estimate retrieval quality from the strongest retrieved chunks.
        """
        if not retrieved_docs:
            return 0.0

        top_docs = sorted(retrieved_docs, key=lambda doc: doc.similarity, reverse=True)[:3]
        return sum(doc.similarity for doc in top_docs) / len(top_docs)

    def _split_sentences(self, text: str) -> List[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [sentence.strip() for sentence in sentences if sentence.strip()]

    def _content_tokens(self, text: str) -> List[str]:
        tokens = re.findall(r"[a-z0-9][a-z0-9+\-_.:/]*", text.lower())
        return [token for token in tokens if len(token) > 2 and token not in self.STOPWORDS]

    def _build_bigrams(self, tokens: List[str]) -> set[str]:
        return {f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)}

    def _sentence_supported(
        self,
        sentence: str,
        context_text: str,
        context_tokens: set[str],
        context_bigrams: set[str]
    ) -> Tuple[bool, str]:
        content_tokens = self._content_tokens(sentence)
        if not content_tokens:
            return True, ""

        content_set = set(content_tokens)
        overlap = content_set & context_tokens
        coverage = len(overlap) / len(content_set)

        sentence_lower = sentence.lower()
        bigram_hits = 0
        if len(content_tokens) > 1:
            sentence_bigrams = {
                f"{content_tokens[i]} {content_tokens[i + 1]}"
                for i in range(len(content_tokens) - 1)
            }
            bigram_hits = len(sentence_bigrams & context_bigrams)

        factual_markers = self._extract_factual_markers(sentence_lower)
        unsupported_markers = [marker for marker in factual_markers if marker not in context_text]

        supported = coverage >= 0.30 or (coverage >= 0.20 and bigram_hits > 0)
        if unsupported_markers and coverage < 0.45:
            supported = False

        if supported:
            return True, ""

        detail = sentence.strip()
        if unsupported_markers:
            detail = f"Unsupported claim: {detail}"
        else:
            detail = f"Low support: {detail}"
        return False, detail

    def _extract_factual_markers(self, sentence: str) -> List[str]:
        markers = re.findall(r"\b\d+(?:\.\d+)?%?\b", sentence)
        markers.extend(re.findall(r"\b(?:19|20)\d{2}\b", sentence))
        markers.extend(re.findall(r"\b[a-z0-9]+(?:\.[a-z0-9]+)+\b", sentence))
        return [marker.lower() for marker in markers]
    
    def _parse_verification(self, verification_text: str) -> Dict:
        """Parse LLM verification output."""
        result = {
            'verified': False,
            'confidence': 0.5,
            'issues': []
        }

        logger.info("DEBUG: Starting verification parsing...")
        text = verification_text.strip()
        lowered = text.lower()

        # Parse verified status (supports both legacy and new formats)
        verified_true_patterns = [
            r'verified\s*:\s*(yes|true)',
            r'verified\s*:\s*verified',
            r'verdict\s*:\s*(yes|true|verified)'
        ]
        verified_false_patterns = [
            r'verified\s*:\s*(no|false)',
            r'verified\s*:\s*not\s*verified',
            r'verdict\s*:\s*(no|false|not\s*verified)'
        ]

        if any(re.search(pattern, lowered) for pattern in verified_true_patterns):
            result['verified'] = True
            logger.info("DEBUG: Parsed verified=True")
        elif any(re.search(pattern, lowered) for pattern in verified_false_patterns):
            result['verified'] = False
            logger.info("DEBUG: Parsed verified=False")

        # Parse confidence (supports "Confidence:" and "Confidence score:")
        confidence_patterns = [
            r'confidence(?:\s*score|\s*level)?\s*:\s*([01](?:\.\d+)?)',
            r'confidence\s*=\s*([01](?:\.\d+)?)',
            r'([01](?:\.\d+)?)\s*confidence'
        ]
        for pattern in confidence_patterns:
            confidence_match = re.search(pattern, lowered)
            if confidence_match:
                try:
                    parsed_confidence = float(confidence_match.group(1))
                    result['confidence'] = max(0.0, min(1.0, parsed_confidence))
                    logger.info(f"DEBUG: Confidence extracted: {result['confidence']}")
                    break
                except ValueError:
                    continue

        # Parse issues block
        issues_match = re.search(
            r'issues?\s*:\s*(.*?)(?:\n[A-Za-z][A-Za-z ]*:\s*|\Z)',
            text,
            re.DOTALL | re.IGNORECASE
        )
        if issues_match:
            issues_text = issues_match.group(1).strip()
            if issues_text and issues_text.lower() not in ['none', 'no issues', '[]', '- none']:
                issue_lines = [line.strip("-• \t") for line in issues_text.splitlines() if line.strip()]
                normalized = [line for line in issue_lines if line.lower() not in ['none', 'no issues', '[]']]
                if normalized:
                    result['issues'] = normalized
        
        return result
    
    def detect_information_gaps(
        self,
        query: str,
        retrieved_docs: List[RetrievalResult]
    ) -> Tuple[bool, List[str]]:
        """
        Detect if there are information gaps in the retrieved documents.
        Returns: (has_gaps, list of missing aspects)
        """
        if not retrieved_docs:
            return True, ["No relevant documents retrieved"]
        
        # Simple check: if too few results or low similarity
        gaps = []
        
        if len(retrieved_docs) < 2:
            gaps.append("Very few relevant documents found")
        
        avg_similarity = sum(doc.similarity for doc in retrieved_docs) / len(retrieved_docs)
        if avg_similarity < 0.5:
            gaps.append(f"Low average similarity: {avg_similarity:.2f}")
        
        # Check if results are diverse (simple check: unique sources)
        unique_sources = len(set(doc.source for doc in retrieved_docs))
        if unique_sources == 1 and len(retrieved_docs) > 1:
            gaps.append("All results from single source - may lack breadth")
        
        return len(gaps) > 0, gaps
    
    def _format_context(self, results: List[RetrievalResult]) -> str:
        """Format results using the shared compact retrieval context format."""
        if not results:
            return ""

        return retrieval_service.format_context(
            results,
            max_tokens=settings.max_context_tokens // 4,
            max_results=settings.verify_context_chunks,
            include_page_hint=False,
            include_created_at=False
        )

    def _extract_page_hint(self, chunk_id: str) -> str:
        """Extract page hint from chunk identifier when available."""
        patterns = [
            r'page[_\- ]?(\d+)',
            r'\bp[_\- ]?(\d+)\b',
            r'chunk[_\- ]?\d+[_\- ]?(\d+)$'
        ]
        lowered = chunk_id.lower()
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                return match.group(1)
        return ""


# Global verification service instance
verification_service = VerificationService()
