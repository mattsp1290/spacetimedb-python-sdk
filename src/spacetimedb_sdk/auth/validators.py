"""
Authentication Validators for SpacetimeDB

This module provides validation utilities for authentication tokens
and credentials used in SpacetimeDB connections.
"""

import re
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from .providers import AuthProvider, JWTAuthProvider, IdentityAuthProvider


class ValidationResult:
    """
    Result of a validation operation.
    """
    
    def __init__(
        self,
        is_valid: bool,
        message: str = "",
        details: Optional[Dict[str, Any]] = None
    ):
        self.is_valid = is_valid
        self.message = message
        self.details = details or {}
    
    def __bool__(self) -> bool:
        return self.is_valid
    
    def __str__(self) -> str:
        return f"ValidationResult(valid={self.is_valid}, message='{self.message}')"


class TokenValidator:
    """
    Validator for authentication tokens.
    
    This class provides comprehensive validation for different types
    of authentication tokens used in SpacetimeDB.
    """
    
    # Common token patterns
    JWT_PATTERN = re.compile(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$')
    IDENTITY_PATTERN = re.compile(r'^[a-fA-F0-9]{16,}$')  # Hex string, at least 16 chars
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(f"{__name__}.TokenValidator")
    
    def validate_jwt_token(
        self,
        token: str,
        provider: Optional[JWTAuthProvider] = None,
        strict: bool = True
    ) -> ValidationResult:
        """
        Validate a JWT token.
        
        Args:
            token: JWT token to validate
            provider: JWT provider for validation (optional)
            strict: Whether to perform strict validation
            
        Returns:
            ValidationResult with validation outcome
        """
        if not token:
            return ValidationResult(False, "Token is empty")
        
        # Check JWT format
        if not self.JWT_PATTERN.match(token):
            return ValidationResult(False, "Invalid JWT format")
        
        # Basic structure validation
        parts = token.split('.')
        if len(parts) != 3:
            return ValidationResult(False, "JWT must have exactly 3 parts")
        
        try:
            # Try to decode header and payload
            import jwt
            import base64
            
            # Decode header
            header_data = base64.urlsafe_b64decode(parts[0] + '==')
            header = jwt.utils.base64url_decode(parts[0])
            
            # Decode payload
            payload = jwt.decode(token, options={"verify_signature": False})
            
            details = {
                'header': header,
                'payload': payload,
                'token_type': 'jwt'
            }
            
            # Check expiration
            if 'exp' in payload:
                exp_timestamp = payload['exp']
                if datetime.utcnow().timestamp() > exp_timestamp:
                    return ValidationResult(
                        False,
                        "Token has expired",
                        details
                    )
            
            # Use provider for additional validation if available
            if provider and strict:
                if not provider.validate_token(token):
                    return ValidationResult(
                        False,
                        "Token failed provider validation",
                        details
                    )
            
            return ValidationResult(True, "Valid JWT token", details)
            
        except Exception as e:
            return ValidationResult(False, f"Token validation error: {str(e)}")
    
    def validate_identity_token(
        self,
        token: str,
        provider: Optional[IdentityAuthProvider] = None,
        strict: bool = True
    ) -> ValidationResult:
        """
        Validate an identity token.
        
        Args:
            token: Identity token to validate
            provider: Identity provider for validation (optional)
            strict: Whether to perform strict validation
            
        Returns:
            ValidationResult with validation outcome
        """
        if not token:
            return ValidationResult(False, "Token is empty")
        
        # Check identity format
        if not self.IDENTITY_PATTERN.match(token):
            return ValidationResult(False, "Invalid identity format (must be hex string, 16+ chars)")
        
        # Length validation
        if len(token) < 16:
            return ValidationResult(False, "Identity token too short (minimum 16 characters)")
        
        if len(token) > 128:
            return ValidationResult(False, "Identity token too long (maximum 128 characters)")
        
        details = {
            'identity': token,
            'token_type': 'identity',
            'length': len(token)
        }
        
        # Use provider for additional validation if available
        if provider and strict:
            if not provider.validate_token(token):
                return ValidationResult(
                    False,
                    "Token failed provider validation",
                    details
                )
        
        return ValidationResult(True, "Valid identity token", details)
    
    def validate_token(
        self,
        token: str,
        token_type: Optional[str] = None,
        provider: Optional[AuthProvider] = None,
        strict: bool = True
    ) -> ValidationResult:
        """
        Validate a token, auto-detecting type if not specified.
        
        Args:
            token: Token to validate
            token_type: Type of token ('jwt' or 'identity'), auto-detected if None
            provider: Auth provider for validation (optional)
            strict: Whether to perform strict validation
            
        Returns:
            ValidationResult with validation outcome
        """
        if not token:
            return ValidationResult(False, "Token is empty")
        
        # Auto-detect token type if not specified
        if token_type is None:
            if self.JWT_PATTERN.match(token):
                token_type = 'jwt'
            elif self.IDENTITY_PATTERN.match(token):
                token_type = 'identity'
            else:
                return ValidationResult(False, "Unknown token format")
        
        # Validate based on type
        if token_type.lower() == 'jwt':
            jwt_provider = provider if isinstance(provider, JWTAuthProvider) else None
            return self.validate_jwt_token(token, jwt_provider, strict)
        elif token_type.lower() == 'identity':
            identity_provider = provider if isinstance(provider, IdentityAuthProvider) else None
            return self.validate_identity_token(token, identity_provider, strict)
        else:
            return ValidationResult(False, f"Unsupported token type: {token_type}")
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """
        Get information about a token.
        
        Args:
            token: Token to analyze
            
        Returns:
            Dictionary with token information
        """
        info = {
            'token': token[:16] + '...' if len(token) > 16 else token,
            'length': len(token),
            'type': 'unknown'
        }
        
        # Detect token type
        if self.JWT_PATTERN.match(token):
            info['type'] = 'jwt'
            
            try:
                import jwt
                payload = jwt.decode(token, options={"verify_signature": False})
                info.update({
                    'identity': payload.get('sub'),
                    'issued_at': payload.get('iat'),
                    'expires_at': payload.get('exp'),
                    'audience': payload.get('aud'),
                    'issuer': payload.get('iss')
                })
            except Exception as e:
                info['decode_error'] = str(e)
                
        elif self.IDENTITY_PATTERN.match(token):
            info['type'] = 'identity'
            info['identity'] = token
        
        return info


class CredentialsValidator:
    """
    Validator for authentication credentials.
    
    This class provides validation for complete credential sets
    including identity, tokens, and connection parameters.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(f"{__name__}.CredentialsValidator")
        self.token_validator = TokenValidator(logger)
    
    def validate_credentials(
        self,
        identity: str,
        token: str,
        host: str,
        database: str,
        additional_checks: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate a complete set of credentials.
        
        Args:
            identity: Identity string
            token: Authentication token
            host: Server host
            database: Database name
            additional_checks: Additional validation parameters
            
        Returns:
            ValidationResult with validation outcome
        """
        errors = []
        details = {}
        
        # Validate identity
        if not identity:
            errors.append("Identity is required")
        elif not re.match(r'^[a-fA-F0-9]{16,}$', identity):
            errors.append("Identity must be a hex string with at least 16 characters")
        else:
            details['identity_valid'] = True
        
        # Validate token
        token_result = self.token_validator.validate_token(token)
        if not token_result.is_valid:
            errors.append(f"Token validation failed: {token_result.message}")
        else:
            details['token_valid'] = True
            details['token_info'] = token_result.details
        
        # Validate host
        if not host:
            errors.append("Host is required")
        elif not self._is_valid_host(host):
            errors.append("Host format is invalid")
        else:
            details['host_valid'] = True
        
        # Validate database
        if not database:
            errors.append("Database name is required")
        elif not self._is_valid_database_name(database):
            errors.append("Database name format is invalid")
        else:
            details['database_valid'] = True
        
        # Additional checks
        if additional_checks:
            for check_name, check_value in additional_checks.items():
                if check_name == 'token_not_expired':
                    if check_value and 'exp' in token_result.details.get('payload', {}):
                        exp_timestamp = token_result.details['payload']['exp']
                        if datetime.utcnow().timestamp() > exp_timestamp:
                            errors.append("Token has expired")
                        else:
                            details['token_not_expired'] = True
        
        if errors:
            return ValidationResult(False, "; ".join(errors), details)
        
        return ValidationResult(True, "Valid credentials", details)
    
    def _is_valid_host(self, host: str) -> bool:
        """Check if host format is valid."""
        # Basic host validation
        if not host:
            return False
        
        # Allow localhost, IP addresses, and domain names with optional port
        patterns = [
            r'^localhost(:\d+)?$',
            r'^127\.0\.0\.1(:\d+)?$',
            r'^(\d{1,3}\.){3}\d{1,3}(:\d+)?$',  # IP address
            r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(:\d+)?$',  # Domain name
            r'^[a-zA-Z0-9.-]+(:\d+)?$'  # Simple hostname
        ]
        
        return any(re.match(pattern, host) for pattern in patterns)
    
    def _is_valid_database_name(self, database: str) -> bool:
        """Check if database name format is valid."""
        if not database:
            return False
        
        # Database name should be alphanumeric with allowed special characters
        pattern = r'^[a-zA-Z0-9_-]+$'
        return re.match(pattern, database) is not None
    
    def validate_connection_parameters(
        self,
        host: str,
        database: str,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate connection parameters.
        
        Args:
            host: Server host
            database: Database name
            additional_params: Additional connection parameters
            
        Returns:
            ValidationResult with validation outcome
        """
        errors = []
        details = {}
        
        # Validate host
        if not self._is_valid_host(host):
            errors.append("Invalid host format")
        else:
            details['host_valid'] = True
        
        # Validate database
        if not self._is_valid_database_name(database):
            errors.append("Invalid database name format")
        else:
            details['database_valid'] = True
        
        # Validate additional parameters
        if additional_params:
            for param_name, param_value in additional_params.items():
                if param_name == 'timeout' and isinstance(param_value, (int, float)):
                    if param_value <= 0:
                        errors.append("Timeout must be positive")
                    else:
                        details['timeout_valid'] = True
                elif param_name == 'max_retries' and isinstance(param_value, int):
                    if param_value < 0:
                        errors.append("Max retries must be non-negative")
                    else:
                        details['max_retries_valid'] = True
        
        if errors:
            return ValidationResult(False, "; ".join(errors), details)
        
        return ValidationResult(True, "Valid connection parameters", details)


class SecurityValidator:
    """
    Security-focused validator for authentication components.
    
    This validator focuses on security best practices and potential
    security issues in authentication tokens and credentials.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(f"{__name__}.SecurityValidator")
    
    def check_token_security(self, token: str) -> ValidationResult:
        """
        Check token for security issues.
        
        Args:
            token: Token to check
            
        Returns:
            ValidationResult with security assessment
        """
        warnings = []
        details = {}
        
        # Check token length
        if len(token) < 32:
            warnings.append("Token is shorter than recommended minimum (32 characters)")
        
        # Check for common weak patterns
        if token.lower() in ['test', 'debug', 'admin', 'password', '123456']:
            warnings.append("Token appears to be a weak test value")
        
        # Check for repeated characters
        if len(set(token)) < len(token) * 0.3:
            warnings.append("Token has low entropy (too many repeated characters)")
        
        # Check for obvious patterns
        if token.isdigit():
            warnings.append("Token is all digits (low security)")
        elif token.isalpha():
            warnings.append("Token is all letters (consider mixed alphanumeric)")
        
        # JWT-specific checks
        if '.' in token and len(token.split('.')) == 3:
            try:
                import jwt
                payload = jwt.decode(token, options={"verify_signature": False})
                
                # Check for sensitive data in payload
                sensitive_fields = ['password', 'secret', 'key', 'private']
                for field in sensitive_fields:
                    if any(field in str(value).lower() for value in payload.values()):
                        warnings.append(f"Token payload may contain sensitive data ({field})")
                
                # Check expiration
                if 'exp' not in payload:
                    warnings.append("JWT token has no expiration claim")
                elif payload['exp'] - datetime.utcnow().timestamp() > 365 * 24 * 3600:
                    warnings.append("JWT token has very long expiration (over 1 year)")
                
                details['jwt_payload_size'] = len(str(payload))
                
            except Exception:
                pass
        
        details['token_length'] = len(token)
        details['unique_chars'] = len(set(token))
        details['entropy_ratio'] = len(set(token)) / len(token) if token else 0
        
        if warnings:
            return ValidationResult(False, "; ".join(warnings), details)
        
        return ValidationResult(True, "Token appears secure", details)
    
    def check_storage_security(self, storage_path: str) -> ValidationResult:
        """
        Check storage location for security issues.
        
        Args:
            storage_path: Path to storage location
            
        Returns:
            ValidationResult with security assessment
        """
        import os
        import stat
        from pathlib import Path
        
        warnings = []
        details = {}
        
        path = Path(storage_path)
        
        # Check if path exists
        if not path.exists():
            return ValidationResult(True, "Storage path does not exist yet", details)
        
        # Check file permissions
        if path.is_file():
            file_stat = path.stat()
            mode = file_stat.st_mode
            
            # Check if file is readable by others
            if mode & stat.S_IROTH:
                warnings.append("Storage file is readable by others")
            
            # Check if file is writable by others
            if mode & stat.S_IWOTH:
                warnings.append("Storage file is writable by others")
            
            # Check if file is executable
            if mode & stat.S_IXUSR:
                warnings.append("Storage file is executable (unnecessary)")
            
            details['file_permissions'] = oct(mode)
        
        # Check directory permissions
        if path.is_dir():
            dir_stat = path.stat()
            mode = dir_stat.st_mode
            
            # Check if directory is accessible by others
            if mode & stat.S_IROTH or mode & stat.S_IXOTH:
                warnings.append("Storage directory is accessible by others")
            
            details['directory_permissions'] = oct(mode)
        
        # Check if path is in a secure location
        if '/tmp' in str(path) or '/var/tmp' in str(path):
            warnings.append("Storage location is in temporary directory (security risk)")
        
        details['storage_path'] = str(path)
        
        if warnings:
            return ValidationResult(False, "; ".join(warnings), details)
        
        return ValidationResult(True, "Storage location appears secure", details)