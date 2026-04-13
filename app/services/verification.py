"""
Verification service for hallucination detection and answer validation.
"""
from typing import Dict, List, Tuple
from app.services.llm import llm_service
from app.models.entities import RetrievalResult
from app.core.config import settings
from app.core.text_utils import estimate_tokens, truncate_to_token_limit
import logging
import re

logger = logging.getLogger(__name__)


class VerificationService:
    """Service for verifying answers and detecting hallucinations."""
    
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
                max_tokens=llm_service.get_phase_max_tokens("verify", 300)
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
            grounding_score = self._check_grounding(answer, retrieved_docs)
            parsed['grounding_score'] = grounding_score
            logger.info(f"DEBUG: Grounding score calculated: {grounding_score:.2f}")
            
            # Adjust confidence based on grounding
            original_confidence = parsed['confidence']
            if grounding_score < 0.5:
                parsed['confidence'] = min(parsed['confidence'], 0.5)
                parsed['issues'].append(f"Low grounding score: {grounding_score:.2f}")
                logger.warning(f"DEBUG: Confidence capped from {original_confidence:.2f} to {parsed['confidence']:.2f} due to low grounding")
            
            logger.info(f"Verification: {parsed['verified']}, confidence: {parsed['confidence']:.2f}")
            return parsed
            
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
        if not retrieved_docs or not answer:
            return 0.0
        
        # Extract key phrases from answer (simple approach)
        answer_words = set(answer.lower().split())
        
        # Check overlap with retrieved documents
        total_overlap = 0
        total_words = 0
        
        for doc in retrieved_docs:
            doc_words = set(doc.text.lower().split())
            overlap = len(answer_words & doc_words)
            total_overlap += overlap
            total_words += len(doc_words)
        
        if total_words == 0:
            return 0.0
        
        # Calculate grounding score
        grounding_score = min(total_overlap / len(answer_words), 1.0) if answer_words else 0.0
        return grounding_score
    
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
        """Format results into a clear, structured context string."""
        if not results:
            return ""

        parts = []
        for idx, result in enumerate(results, 1):
            page_hint = self._extract_page_hint(result.chunk_id)
            page_line = f"- Page Hint: {page_hint}\n" if page_hint else ""
            parts.append(
                f"=== Source {idx} ===\n"
                f"- Source: {result.source}\n"
                f"- Chunk ID: {result.chunk_id}\n"
                f"- Similarity Score: {result.similarity:.3f}\n"
                f"{page_line}"
                f"Content:\n{result.text}\n"
                f"=== End Source {idx} ==="
            )
        return "\n\n".join(parts) + "\n\nEND OF CONTEXT"

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
