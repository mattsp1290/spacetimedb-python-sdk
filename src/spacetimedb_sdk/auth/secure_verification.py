"""
Secure Authentication Verification Module

This module provides secure credential verification functions that are resistant to timing attacks.
All credential comparison operations use constant-time algorithms to prevent information leakage
through timing analysis.

Security Features:
- Constant-time credential comparison using secrets.compare_digest()
- Protection against timing attack vulnerabilities
- Secure token validation with consistent execution timing
- Authentication event logging without credential exposure
- Rate limiting for authentication attempts

Critical Security Note:
This module addresses CVE-style timing attack vulnerabilities where attackers can determine
credential validity by measuring execution time differences during string comparisons.
"""

import secrets
import hashlib
import time
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from .security_logger import get_security_logger, SecurityEventType
    HAS_SECURITY_LOGGER = True
except ImportError:
    HAS_SECURITY_LOGGER = False
    get_security_logger = None
    SecurityEventType = None


class VerificationResult(Enum):
    """Authentication verification results."""
    SUCCESS = "success"
    FAILURE = "failure"
    RATE_LIMITED = "rate_limited"
    INVALID_FORMAT = "invalid_format"


@dataclass
class SecureCredentials:
    """Secure credential container."""
    stored_hash: str
    provided_credential: str
    credential_type: str
    
    def __post_init__(self):
        """Ensure credentials are strings for comparison."""
        if not isinstance(self.stored_hash, str):
            self.stored_hash = str(self.stored_hash)
        if not isinstance(self.provided_credential, str):
            self.provided_credential = str(self.provided_credential)


@dataclass
class TokenFormatResult:
    """Result of token format verification."""
    is_valid: bool
    error: Optional[str] = None


class SecureVerificationManager:
    """
    Manages secure credential verification with timing attack protection.
    
    This class implements constant-time credential verification to prevent
    timing attacks where attackers measure execution time differences to
    determine credential validity.
    """
    
    def __init__(self, rate_limit_window: float = 60.0, max_attempts: int = 5):
        """
        Initialize secure verification manager.
        
        Args:
            rate_limit_window: Time window for rate limiting (seconds)
            max_attempts: Maximum attempts per time window
        """
        self.rate_limit_window = rate_limit_window
        self.max_attempts = max_attempts
        self._attempt_history: Dict[str, list] = {}
        self.logger = logging.getLogger(__name__)
        
    def verify_credentials(
        self,
        stored: str,
        provided: str,
        identifier: Optional[str] = None
    ) -> VerificationResult:
        """
        Constant-time credential verification to prevent timing attacks.
        
        This method uses secrets.compare_digest() to ensure that credential
        comparison takes the same amount of time regardless of where the
        strings differ, preventing timing attack vulnerabilities.
        
        Args:
            stored: Stored credential hash or value
            provided: Provided credential for verification
            identifier: Optional identifier for rate limiting
            
        Returns:
            VerificationResult indicating success or failure
            
        Security Notes:
            - Uses secrets.compare_digest() for constant-time comparison
            - Execution time is consistent regardless of input differences
            - Prevents timing-based credential enumeration attacks
            - Includes rate limiting to prevent brute force attacks
        """
        start_time = time.perf_counter()
        
        # Rate limiting check
        if identifier and self._is_rate_limited(identifier):
            self._log_verification_attempt(identifier, VerificationResult.RATE_LIMITED, start_time)
            return VerificationResult.RATE_LIMITED
        
        # Ensure both values are strings for comparison
        if not isinstance(stored, str) or not isinstance(provided, str):
            self._log_verification_attempt(identifier, VerificationResult.INVALID_FORMAT, start_time)
            return VerificationResult.INVALID_FORMAT
        
        # Constant-time comparison using secrets.compare_digest()
        # This prevents timing attacks by ensuring the comparison takes
        # the same amount of time regardless of where strings differ
        # Convert to bytes to handle Unicode strings properly
        stored_bytes = stored.encode('utf-8')
        provided_bytes = provided.encode('utf-8')
        is_valid = secrets.compare_digest(stored_bytes, provided_bytes)
        
        result = VerificationResult.SUCCESS if is_valid else VerificationResult.FAILURE
        
        # Record attempt for rate limiting
        if identifier:
            self._record_attempt(identifier)
        
        self._log_verification_attempt(identifier, result, start_time)
        
        # Log to security logger if available
        if HAS_SECURITY_LOGGER and get_security_logger:
            duration_ms = (time.perf_counter() - start_time) * 1000
            security_logger = get_security_logger()
            
            if result == VerificationResult.SUCCESS:
                security_logger.log_authentication_success(
                    user_identifier=identifier,
                    duration_ms=duration_ms,
                    metadata={"verification_type": "credential"}
                )
            elif result == VerificationResult.RATE_LIMITED:
                security_logger.log_rate_limiting_event(
                    user_identifier=identifier or "unknown",
                    attempt_count=len(self._attempt_history.get(identifier or "", [])),
                    rate_limit_window=self.rate_limit_window
                )
            else:
                security_logger.log_authentication_failure(
                    user_identifier=identifier,
                    duration_ms=duration_ms,
                    failure_reason=result.value,
                    metadata={"verification_type": "credential"}
                )
        
        return result
    
    def verify_password(
        self,
        stored_hash: str,
        provided_password: str,
        salt: Optional[str] = None,
        identifier: Optional[str] = None
    ) -> VerificationResult:
        """
        Secure password verification with timing attack protection.
        
        Args:
            stored_hash: Stored password hash
            provided_password: Password to verify
            salt: Optional salt for hashing
            identifier: Optional identifier for rate limiting
            
        Returns:
            VerificationResult indicating success or failure
        """
        if salt:
            # Hash the provided password with salt
            provided_hash = self._hash_password(provided_password, salt)
        else:
            provided_hash = provided_password
            
        return self.verify_credentials(stored_hash, provided_hash, identifier)
    
    def verify_token(
        self,
        stored_token: str,
        provided_token: str,
        identifier: Optional[str] = None
    ) -> VerificationResult:
        """
        Secure token verification with timing attack protection.
        
        Args:
            stored_token: Expected token value
            provided_token: Token to verify
            identifier: Optional identifier for rate limiting
            
        Returns:
            VerificationResult indicating success or failure
        """
        # Normalize tokens (strip whitespace, handle None values)
        stored_normalized = (stored_token or "").strip()
        provided_normalized = (provided_token or "").strip()
        
        return self.verify_credentials(stored_normalized, provided_normalized, identifier)
    
    def verify_api_key(
        self,
        stored_key_hash: str,
        provided_key: str,
        identifier: Optional[str] = None
    ) -> VerificationResult:
        """
        Secure API key verification with timing attack protection.
        
        Args:
            stored_key_hash: Stored API key hash
            provided_key: API key to verify
            identifier: Optional identifier for rate limiting
            
        Returns:
            VerificationResult indicating success or failure
        """
        # Hash the provided key for comparison
        provided_key_hash = self._hash_api_key(provided_key)
        
        return self.verify_credentials(stored_key_hash, provided_key_hash, identifier)
    
    def verify_identity_token(
        self,
        expected_identity: str,
        provided_identity: str,
        expected_token: str,
        provided_token: str,
        identifier: Optional[str] = None
    ) -> VerificationResult:
        """
        Secure identity and token verification.
        
        Verifies both identity and token in a constant-time manner to prevent
        timing attacks that could reveal information about either component.
        
        Args:
            expected_identity: Expected identity value
            provided_identity: Provided identity
            expected_token: Expected token value  
            provided_token: Provided token
            identifier: Optional identifier for rate limiting
            
        Returns:
            VerificationResult indicating success or failure
        """
        # Verify both identity and token using constant-time comparison
        # Convert to bytes to handle Unicode strings properly
        expected_identity_bytes = (expected_identity or "").encode('utf-8')
        provided_identity_bytes = (provided_identity or "").encode('utf-8')
        expected_token_bytes = (expected_token or "").encode('utf-8')
        provided_token_bytes = (provided_token or "").encode('utf-8')
        
        identity_valid = secrets.compare_digest(
            expected_identity_bytes,
            provided_identity_bytes
        )
        token_valid = secrets.compare_digest(
            expected_token_bytes,
            provided_token_bytes
        )
        
        # Both must be valid for success
        overall_valid = identity_valid and token_valid
        
        result = VerificationResult.SUCCESS if overall_valid else VerificationResult.FAILURE
        
        # Record attempt for rate limiting
        if identifier:
            if self._is_rate_limited(identifier):
                return VerificationResult.RATE_LIMITED
            self._record_attempt(identifier)
        
        self._log_verification_attempt(identifier, result, time.perf_counter())
        return result
    
    def verify_token_format(self, token: str) -> TokenFormatResult:
        """
        Verify token format for SpacetimeDB authentication.
        
        This method validates that a token has the expected format for SpacetimeDB.
        Currently performs basic validation but can be extended for more specific
        format requirements.
        
        Args:
            token: Token string to verify
            
        Returns:
            TokenFormatResult with validation outcome
        """
        start_time = time.perf_counter()
        
        try:
            # Basic token validation
            if not token or not isinstance(token, str):
                return TokenFormatResult(
                    is_valid=False,
                    error="Token must be a non-empty string"
                )
            
            # Remove whitespace
            token = token.strip()
            
            if not token:
                return TokenFormatResult(
                    is_valid=False,
                    error="Token cannot be empty or whitespace only"
                )
            
            # Check minimum length (SpacetimeDB tokens are typically JWTs or similar)
            if len(token) < 10:
                return TokenFormatResult(
                    is_valid=False,
                    error="Token too short - minimum 10 characters required"
                )
            
            # Check maximum reasonable length to prevent DoS
            if len(token) > 10000:
                return TokenFormatResult(
                    is_valid=False,
                    error="Token too long - maximum 10000 characters allowed"
                )
            
            # Check for obviously invalid characters (control characters, etc.)
            if any(ord(c) < 32 for c in token if c not in '\t\n\r'):
                return TokenFormatResult(
                    is_valid=False,
                    error="Token contains invalid control characters"
                )
            
            # Check for dangerous patterns similar to the client validation
            import re
            dangerous_patterns = [
                r'<script',  # XSS attempts
                r'javascript:',  # JavaScript injection
                r'[\r\n]',  # CRLF injection
                r'\x00',  # Null bytes
                r'[;&|`$]',  # Command injection
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, token, re.IGNORECASE):
                    return TokenFormatResult(
                        is_valid=False,
                        error=f"Token contains dangerous pattern: {pattern}"
                    )
            
            # Additional format validation could be added here for specific
            # SpacetimeDB token formats (e.g., JWT structure validation)
            
            return TokenFormatResult(is_valid=True)
            
        except Exception as e:
            return TokenFormatResult(
                is_valid=False,
                error=f"Token validation error: {str(e)}"
            )
        finally:
            # Log the verification attempt
            duration = time.perf_counter() - start_time
            self.logger.debug(f"Token format verification took {duration*1000:.2f}ms")
    
    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password with salt using SHA-256."""
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def _hash_api_key(self, api_key: str) -> str:
        """Hash API key using SHA-256."""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def _is_rate_limited(self, identifier: str) -> bool:
        """Check if identifier is rate limited."""
        now = time.time()
        
        if identifier not in self._attempt_history:
            return False
        
        # Clean old attempts outside the window
        self._attempt_history[identifier] = [
            attempt_time for attempt_time in self._attempt_history[identifier]
            if now - attempt_time < self.rate_limit_window
        ]
        
        return len(self._attempt_history[identifier]) >= self.max_attempts
    
    def _record_attempt(self, identifier: str) -> None:
        """Record authentication attempt for rate limiting."""
        now = time.time()
        
        if identifier not in self._attempt_history:
            self._attempt_history[identifier] = []
        
        self._attempt_history[identifier].append(now)
    
    def _log_verification_attempt(
        self,
        identifier: Optional[str],
        result: VerificationResult,
        start_time: float
    ) -> None:
        """
        Log verification attempt without exposing sensitive data.
        
        Args:
            identifier: Optional identifier (logged if present)
            result: Verification result
            start_time: Start time for duration calculation
        """
        duration = time.perf_counter() - start_time
        
        # Create sanitized log entry
        log_data = {
            "verification_result": result.value,
            "duration_ms": round(duration * 1000, 2),
            "timestamp": time.time()
        }
        
        if identifier:
            # Log only a hash of the identifier for privacy
            identifier_hash = hashlib.sha256(identifier.encode()).hexdigest()[:8]
            log_data["identifier_hash"] = identifier_hash
        
        # Log at appropriate level
        if result == VerificationResult.SUCCESS:
            self.logger.info("Authentication verification succeeded", extra=log_data)
        elif result == VerificationResult.RATE_LIMITED:
            self.logger.warning("Authentication rate limited", extra=log_data)
        else:
            self.logger.warning("Authentication verification failed", extra=log_data)
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics for monitoring."""
        total_identifiers = len(self._attempt_history)
        total_attempts = sum(len(attempts) for attempts in self._attempt_history.values())
        
        return {
            "total_identifiers_tracked": total_identifiers,
            "total_attempts_in_window": total_attempts,
            "rate_limit_window_seconds": self.rate_limit_window,
            "max_attempts_per_window": self.max_attempts,
            "currently_rate_limited": sum(
                1 for identifier in self._attempt_history.keys()
                if self._is_rate_limited(identifier)
            )
        }


# Convenience functions for backward compatibility and ease of use
def verify_credentials_secure(stored: str, provided: str) -> bool:
    """
    Convenience function for secure credential verification.
    
    This function provides constant-time comparison that works with both
    ASCII and Unicode strings by converting to UTF-8 bytes before comparison.
    
    Args:
        stored: Stored credential
        provided: Provided credential
        
    Returns:
        True if credentials match, False otherwise
        
    Note:
        This is a simplified interface. For production use with rate limiting
        and logging, use SecureVerificationManager directly.
        
    Security Notes:
        - Uses secrets.compare_digest() for constant-time comparison
        - Handles Unicode strings by encoding to UTF-8 bytes
        - Prevents timing attacks on both ASCII and non-ASCII strings
    """
    if not isinstance(stored, str) or not isinstance(provided, str):
        return False
    
    # Convert strings to UTF-8 bytes for comparison to handle Unicode
    # secrets.compare_digest() only supports ASCII strings or bytes
    stored_bytes = stored.encode('utf-8')
    provided_bytes = provided.encode('utf-8')
    
    return secrets.compare_digest(stored_bytes, provided_bytes)


def verify_password_secure(stored_hash: str, provided_password: str, salt: str = "") -> bool:
    """
    Convenience function for secure password verification.
    
    Args:
        stored_hash: Stored password hash
        provided_password: Password to verify
        salt: Salt for hashing
        
    Returns:
        True if password is valid, False otherwise
    """
    if not all(isinstance(x, str) for x in [stored_hash, provided_password, salt]):
        return False
    
    provided_hash = hashlib.sha256((provided_password + salt).encode()).hexdigest()
    return secrets.compare_digest(stored_hash, provided_hash)


def verify_token_secure(stored_token: str, provided_token: str) -> bool:
    """
    Convenience function for secure token verification.
    
    This function provides constant-time comparison that works with both
    ASCII and Unicode strings by converting to UTF-8 bytes before comparison.
    
    Args:
        stored_token: Expected token
        provided_token: Token to verify
        
    Returns:
        True if tokens match, False otherwise
        
    Security Notes:
        - Uses secrets.compare_digest() for constant-time comparison
        - Handles Unicode strings by encoding to UTF-8 bytes
        - Normalizes whitespace before comparison
        - Prevents timing attacks on both ASCII and non-ASCII strings
    """
    if not isinstance(stored_token, str) or not isinstance(provided_token, str):
        return False
    
    # Normalize tokens (strip whitespace)
    stored_normalized = stored_token.strip()
    provided_normalized = provided_token.strip()
    
    # Convert strings to UTF-8 bytes for comparison to handle Unicode
    # secrets.compare_digest() only supports ASCII strings or bytes
    stored_bytes = stored_normalized.encode('utf-8')
    provided_bytes = provided_normalized.encode('utf-8')
    
    return secrets.compare_digest(stored_bytes, provided_bytes)


# Global instance for easy access
_global_verification_manager = SecureVerificationManager()


def get_global_verification_manager() -> SecureVerificationManager:
    """Get the global verification manager instance."""
    return _global_verification_manager


def set_global_verification_manager(manager: SecureVerificationManager) -> None:
    """Set a custom global verification manager."""
    global _global_verification_manager
    _global_verification_manager = manager