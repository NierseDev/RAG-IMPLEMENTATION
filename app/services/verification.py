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
            max_context_tokens = settings.max_context_tokens // 3  # Reserve space for query and answer
            
            if context_tokens > max_context_tokens:
                logger.warning(f"Verification context ({context_tokens} tokens) exceeds limit. Truncating.")
                context = truncate_to_token_limit(context, max_context_tokens)
            
            # Use LLM to verify
            verification_prompt = llm_service.create_verify_prompt(query, answer, context)
            verification_result = await llm_service.generate(
                verification_prompt,
                temperature=0.3,  # Low temperature for consistency
                max_tokens=300
            )
            
            # Parse verification result
            parsed = self._parse_verification(verification_result)
            
            # Additional checks
            grounding_score = self._check_grounding(answer, retrieved_docs)
            parsed['grounding_score'] = grounding_score
            
            # Adjust confidence based on grounding
            if grounding_score < 0.5:
                parsed['confidence'] = min(parsed['confidence'], 0.5)
                parsed['issues'].append(f"Low grounding score: {grounding_score:.2f}")
            
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
        
        # Parse verified status
        if re.search(r'verified:\s*(yes|true)', verification_text.lower()):
            result['verified'] = True
        
        # Parse confidence
        confidence_match = re.search(r'confidence:\s*([0-9.]+)', verification_text.lower())
        if confidence_match:
            try:
                result['confidence'] = float(confidence_match.group(1))
            except ValueError:
                pass
        
        # Parse issues
        issues_match = re.search(r'issues?:(.*?)(?:\n\n|\Z)', verification_text, re.DOTALL | re.IGNORECASE)
        if issues_match:
            issues_text = issues_match.group(1).strip()
            if issues_text and issues_text.lower() not in ['none', 'no issues', '[]']:
                result['issues'] = [issues_text]
        
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
        """Format results into context string with length awareness."""
        if not results:
            return ""
        
        parts = [f"[{result.source}] {result.text}" for result in results]
        return "\n\n".join(parts)


# Global verification service instance
verification_service = VerificationService()
