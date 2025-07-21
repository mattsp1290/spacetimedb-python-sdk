"""
Comprehensive Input Validation Framework for SpacetimeDB Python SDK

This module provides advanced security validation to prevent injection attacks
and resource exhaustion. It implements multiple layers of protection:

1. SQL injection prevention with advanced pattern detection
2. Protocol message validation for all input fields  
3. Resource exhaustion protection (query complexity, message size, execution time)
4. Sanitization and normalization utilities

Security Features:
- Advanced regex patterns for SQL injection detection
- Query complexity analysis to prevent expensive operations
- Allowlist validation for permitted SQL operations
- Comprehensive logging of attack attempts
- Table name validation (alphanumeric + underscore only)
- Client ID format validation
- Message size limits and validation
- Query length limits
- Execution time limits
- Rate limiting for expensive operations

Author: SpacetimeDB Security Team
"""

import re
import time
import hashlib
import threading
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
import logging

# Configure security logger
security_logger = logging.getLogger('spacetimedb.security')
security_logger.setLevel(logging.INFO)


class AttackType(Enum):
    """Types of detected security attacks."""
    SQL_INJECTION = "sql_injection"
    PROTOCOL_INJECTION = "protocol_injection"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    BUFFER_OVERFLOW = "buffer_overflow"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    MALFORMED_INPUT = "malformed_input"
    UNAUTHORIZED_OPERATION = "unauthorized_operation"


@dataclass
class SecurityViolation:
    """Represents a detected security violation."""
    attack_type: AttackType
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    field_name: Optional[str] = None
    original_value: Optional[str] = None
    detected_patterns: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    client_identifier: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'attack_type': self.attack_type.value,
            'severity': self.severity,
            'description': self.description,
            'field_name': self.field_name,
            'original_value': self.original_value[:100] if self.original_value else None,
            'detected_patterns': self.detected_patterns,
            'timestamp': self.timestamp,
            'client_identifier': self.client_identifier
        }


class SecurityValidationError(Exception):
    """Exception raised when security validation fails."""
    
    def __init__(self, message: str, violation: SecurityViolation):
        super().__init__(message)
        self.violation = violation
        self.message = message


@dataclass
class SecurityConfig:
    """Configuration for security validation."""
    # SQL Security Limits
    max_query_length: int = 4096  # 4KB
    max_query_complexity_score: int = 1000
    max_execution_time_seconds: int = 30
    max_result_size_bytes: int = 100 * 1024 * 1024  # 100MB
    
    # Protocol Message Limits
    max_table_name_length: int = 64
    max_client_id_length: int = 128
    max_message_size_bytes: int = 1024 * 1024  # 1MB
    max_array_length: int = 10000
    
    # Rate Limiting
    rate_limit_window_seconds: int = 60
    max_requests_per_window: int = 1000
    max_expensive_operations_per_window: int = 100
    
    # Pattern Detection
    enable_advanced_sql_detection: bool = True
    enable_protocol_validation: bool = True
    enable_resource_protection: bool = True
    log_security_violations: bool = True
    
    # Allowlists
    allowed_sql_operations: Set[str] = field(default_factory=lambda: {'SELECT'})
    allowed_table_name_pattern: str = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
    allowed_client_id_pattern: str = r'^[a-zA-Z0-9\-_]+$'


class SQLSecurityValidator:
    """
    Advanced SQL security validator with comprehensive injection detection.
    
    Features:
    - Advanced regex patterns for SQL injection detection
    - Query complexity analysis to prevent expensive operations
    - Allowlist validation for permitted SQL operations
    - Comprehensive logging of attack attempts
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self._init_injection_patterns()
        self._init_complexity_rules()
        
    def _init_injection_patterns(self):
        """Initialize comprehensive SQL injection detection patterns."""
        self.injection_patterns = {
            # Union-based attacks
            'union_select': re.compile(
                r'\bunion\b.*?\bselect\b', 
                re.IGNORECASE | re.DOTALL
            ),
            
            # Comment injection
            'sql_comments': re.compile(
                r'(?:--|#|/\*|\*/)', 
                re.IGNORECASE
            ),
            
            # Stacked queries  
            'stacked_queries': re.compile(
                r';\s*(?:drop|delete|insert|update|create|alter|truncate|exec|execute)\b',
                re.IGNORECASE
            ),
            
            # Boolean logic manipulation
            'boolean_tautology': re.compile(
                r'\b(?:or|and)\s+(?:\d+\s*[=<>!]+\s*\d+|true|false|1\s*=\s*1|0\s*=\s*0)\b',
                re.IGNORECASE
            ),
            
            # Time-based injection
            'time_based': re.compile(
                r'\b(?:sleep|waitfor|delay|benchmark)\s*\(',
                re.IGNORECASE
            ),
            
            # Function call injection
            'dangerous_functions': re.compile(
                r'\b(?:char|ascii|ord|hex|unhex|load_file|into\s+outfile|dumpfile)\s*\(',
                re.IGNORECASE
            ),
            
            # Information schema access
            'info_schema': re.compile(
                r'\b(?:information_schema|sysobjects|syscolumns|mysql\.user)\b',
                re.IGNORECASE
            ),
            
            # Error-based injection
            'error_based': re.compile(
                r'\b(?:cast|convert|extract)\s*\(',
                re.IGNORECASE
            ),
            
            # String manipulation attacks
            'string_manipulation': re.compile(
                r"(?:'.*?'.*?'|\".*?\".*?\"|0x[0-9a-f]+)",
                re.IGNORECASE
            ),
            
            # Blind SQL injection
            'blind_injection': re.compile(
                r'\b(?:if|case|when|exists|having)\s*\(',
                re.IGNORECASE
            ),
            
            # System command execution
            'system_commands': re.compile(
                r'\b(?:xp_cmdshell|sp_execute|exec\s+master|openrowset)\b',
                re.IGNORECASE
            )
        }
    
    def _init_complexity_rules(self):
        """Initialize query complexity scoring rules."""
        self.complexity_scores = {
            'join': 10,
            'subquery': 15,
            'union': 20,
            'like': 5,
            'regex': 10,
            'group_by': 5,
            'order_by': 3,
            'having': 8,
            'distinct': 3,
            'function_call': 2
        }
    
    def validate_query(self, query: str, client_id: Optional[str] = None) -> Tuple[bool, List[SecurityViolation]]:
        """
        Validate SQL query for security threats.
        
        Args:
            query: SQL query to validate
            client_id: Optional client identifier for tracking
            
        Returns:
            Tuple of (is_valid, violations_list)
        """
        violations = []
        
        if not isinstance(query, str):
            violation = SecurityViolation(
                attack_type=AttackType.MALFORMED_INPUT,
                severity='medium',
                description=f'Query must be string, got {type(query).__name__}',
                field_name='query',
                original_value=str(query),
                client_identifier=client_id
            )
            violations.append(violation)
            return False, violations
            
        # Check for empty query
        if not query.strip():
            violation = SecurityViolation(
                attack_type=AttackType.MALFORMED_INPUT,
                severity='medium',
                description='SQL query cannot be empty',
                field_name='query',
                original_value=query,
                client_identifier=client_id
            )
            violations.append(violation)
            
        # Check query length
        if len(query) > self.config.max_query_length:
            violation = SecurityViolation(
                attack_type=AttackType.BUFFER_OVERFLOW,
                severity='high',
                description=f'Query length {len(query)} exceeds limit {self.config.max_query_length}',
                field_name='query',
                original_value=query,
                client_identifier=client_id
            )
            violations.append(violation)
            
        # Check for injection patterns
        injection_violations = self._check_injection_patterns(query, client_id)
        violations.extend(injection_violations)
        
        # Check query complexity
        complexity_violations = self._check_query_complexity(query, client_id)
        violations.extend(complexity_violations)
        
        # Check allowed operations
        operation_violations = self._check_allowed_operations(query, client_id)
        violations.extend(operation_violations)
        
        # Log violations
        if violations and self.config.log_security_violations:
            self._log_violations(violations)
            
        return len(violations) == 0, violations
    
    def _check_injection_patterns(self, query: str, client_id: Optional[str]) -> List[SecurityViolation]:
        """Check for SQL injection patterns."""
        violations = []
        
        for pattern_name, pattern in self.injection_patterns.items():
            matches = pattern.findall(query)
            if matches:
                violation = SecurityViolation(
                    attack_type=AttackType.SQL_INJECTION,
                    severity='critical',
                    description=f'SQL injection pattern detected: {pattern_name}',
                    field_name='query',
                    original_value=query,
                    detected_patterns=[pattern_name] + matches,
                    client_identifier=client_id
                )
                violations.append(violation)
                
        return violations
    
    def _check_query_complexity(self, query: str, client_id: Optional[str]) -> List[SecurityViolation]:
        """Check query complexity to prevent resource exhaustion."""
        violations = []
        score = 0
        detected_features = []
        
        query_lower = query.lower()
        
        # Count joins
        join_count = len(re.findall(r'\bjoin\b', query_lower))
        if join_count > 0:
            score += join_count * self.complexity_scores['join']
            detected_features.append(f'{join_count} joins')
        
        # Count subqueries
        subquery_count = query_lower.count('(select')
        if subquery_count > 0:
            score += subquery_count * self.complexity_scores['subquery']
            detected_features.append(f'{subquery_count} subqueries')
        
        # Count unions
        union_count = len(re.findall(r'\bunion\b', query_lower))
        if union_count > 0:
            score += union_count * self.complexity_scores['union']
            detected_features.append(f'{union_count} unions')
            
        # Count LIKE operations
        like_count = len(re.findall(r'\blike\b', query_lower))
        if like_count > 0:
            score += like_count * self.complexity_scores['like']
            detected_features.append(f'{like_count} like operations')
            
        # Count function calls
        function_count = len(re.findall(r'\w+\s*\(', query))
        if function_count > 0:
            score += function_count * self.complexity_scores['function_call']
            detected_features.append(f'{function_count} function calls')
        
        if score > self.config.max_query_complexity_score:
            violation = SecurityViolation(
                attack_type=AttackType.RESOURCE_EXHAUSTION,
                severity='high',
                description=f'Query complexity score {score} exceeds limit {self.config.max_query_complexity_score}',
                field_name='query',
                original_value=query,
                detected_patterns=detected_features,
                client_identifier=client_id
            )
            violations.append(violation)
            
        return violations
    
    def _check_allowed_operations(self, query: str, client_id: Optional[str]) -> List[SecurityViolation]:
        """Check if query uses only allowed SQL operations."""
        violations = []
        
        # Extract SQL operation keywords
        tokens = re.findall(r'\b[a-zA-Z]+\b', query.upper())
        sql_keywords = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE'}
        
        found_operations = [token for token in tokens if token in sql_keywords]
        
        for operation in found_operations:
            if operation not in self.config.allowed_sql_operations:
                violation = SecurityViolation(
                    attack_type=AttackType.UNAUTHORIZED_OPERATION,
                    severity='critical',
                    description=f'Unauthorized SQL operation: {operation}',
                    field_name='query',
                    original_value=query,
                    detected_patterns=[operation],
                    client_identifier=client_id
                )
                violations.append(violation)
                
        return violations
    
    def _log_violations(self, violations: List[SecurityViolation]):
        """Log security violations."""
        for violation in violations:
            security_logger.warning(
                f"Security violation detected: {violation.attack_type.value} - {violation.description}",
                extra={'violation_data': violation.to_dict()}
            )


class ProtocolMessageValidator:
    """
    Protocol message validator for all input fields.
    
    Features:
    - Table name validation (alphanumeric + underscore only)
    - Client ID format validation
    - Message size limits and validation
    - Query length limits
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.table_name_pattern = re.compile(self.config.allowed_table_name_pattern)
        self.client_id_pattern = re.compile(self.config.allowed_client_id_pattern)
    
    def validate_table_name(self, table_name: str, client_id: Optional[str] = None) -> Tuple[bool, List[SecurityViolation]]:
        """Validate table name format and length."""
        violations = []
        
        if not isinstance(table_name, str):
            violation = SecurityViolation(
                attack_type=AttackType.MALFORMED_INPUT,
                severity='medium',
                description=f'Table name must be string, got {type(table_name).__name__}',
                field_name='table_name',
                original_value=str(table_name),
                client_identifier=client_id
            )
            violations.append(violation)
            return False, violations
        
        # Length check
        if len(table_name) > self.config.max_table_name_length:
            violation = SecurityViolation(
                attack_type=AttackType.BUFFER_OVERFLOW,
                severity='medium',
                description=f'Table name length {len(table_name)} exceeds limit {self.config.max_table_name_length}',
                field_name='table_name',
                original_value=table_name,
                client_identifier=client_id
            )
            violations.append(violation)
        
        # Format check
        if not self.table_name_pattern.match(table_name):
            violation = SecurityViolation(
                attack_type=AttackType.PROTOCOL_INJECTION,
                severity='high',
                description=f'Invalid table name format: {table_name}',
                field_name='table_name',
                original_value=table_name,
                client_identifier=client_id
            )
            violations.append(violation)
        
        # Check for SQL injection patterns in table name
        dangerous_chars = re.search(r'[;\'"\\-]', table_name)
        if dangerous_chars:
            violation = SecurityViolation(
                attack_type=AttackType.SQL_INJECTION,
                severity='critical',
                description=f'Dangerous characters in table name: {dangerous_chars.group()}',
                field_name='table_name',
                original_value=table_name,
                client_identifier=client_id
            )
            violations.append(violation)
            
        return len(violations) == 0, violations
    
    def validate_client_id(self, client_id: str) -> Tuple[bool, List[SecurityViolation]]:
        """Validate client ID format and length."""
        violations = []
        
        if not isinstance(client_id, str):
            violation = SecurityViolation(
                attack_type=AttackType.MALFORMED_INPUT,
                severity='medium',
                description=f'Client ID must be string, got {type(client_id).__name__}',
                field_name='client_id',
                original_value=str(client_id)
            )
            violations.append(violation)
            return False, violations
        
        # Length check
        if len(client_id) > self.config.max_client_id_length:
            violation = SecurityViolation(
                attack_type=AttackType.BUFFER_OVERFLOW,
                severity='medium', 
                description=f'Client ID length {len(client_id)} exceeds limit {self.config.max_client_id_length}',
                field_name='client_id',
                original_value=client_id
            )
            violations.append(violation)
        
        # Format check
        if not self.client_id_pattern.match(client_id):
            violation = SecurityViolation(
                attack_type=AttackType.PROTOCOL_INJECTION,
                severity='medium',
                description=f'Invalid client ID format: {client_id}',
                field_name='client_id',
                original_value=client_id
            )
            violations.append(violation)
            
        return len(violations) == 0, violations
    
    def validate_message_size(self, message: Any, client_id: Optional[str] = None) -> Tuple[bool, List[SecurityViolation]]:
        """Validate message size to prevent buffer overflow attacks."""
        violations = []
        
        # Calculate message size
        if isinstance(message, str):
            size = len(message.encode('utf-8'))
        elif isinstance(message, bytes):
            size = len(message)
        elif hasattr(message, '__len__'):
            # Estimate size for containers
            size = len(str(message))
        else:
            # Estimate size for objects
            size = len(str(message))
        
        if size > self.config.max_message_size_bytes:
            violation = SecurityViolation(
                attack_type=AttackType.BUFFER_OVERFLOW,
                severity='high',
                description=f'Message size {size} exceeds limit {self.config.max_message_size_bytes}',
                field_name='message',
                original_value=str(message)[:100] if message else None,
                client_identifier=client_id
            )
            violations.append(violation)
            
        return len(violations) == 0, violations
    
    def validate_query_array(self, queries: List[str], client_id: Optional[str] = None) -> Tuple[bool, List[SecurityViolation]]:
        """Validate array of queries for length and content."""
        violations = []
        
        if not isinstance(queries, (list, tuple)):
            violation = SecurityViolation(
                attack_type=AttackType.MALFORMED_INPUT,
                severity='medium',
                description=f'Queries must be list or tuple, got {type(queries).__name__}',
                field_name='queries',
                original_value=str(queries),
                client_identifier=client_id
            )
            violations.append(violation)
            return False, violations
        
        # Check array length
        if len(queries) > self.config.max_array_length:
            violation = SecurityViolation(
                attack_type=AttackType.RESOURCE_EXHAUSTION,
                severity='high',
                description=f'Query array length {len(queries)} exceeds limit {self.config.max_array_length}',
                field_name='queries',
                original_value=f'Array with {len(queries)} items',
                client_identifier=client_id
            )
            violations.append(violation)
        
        # Check each query
        sql_validator = SQLSecurityValidator(self.config)
        for i, query in enumerate(queries):
            is_valid, query_violations = sql_validator.validate_query(query, client_id)
            for violation in query_violations:
                violation.field_name = f'queries[{i}]'
                violations.append(violation)
                
        return len(violations) == 0, violations


class ResourceProtection:
    """
    Resource protection to prevent DoS attacks.
    
    Features:
    - Query complexity scoring
    - Execution time limits  
    - Result size limits
    - Rate limiting for expensive operations
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.rate_limiter = defaultdict(lambda: deque())
        self.expensive_operations = defaultdict(lambda: deque())
        self._lock = threading.Lock()
    
    def check_rate_limit(self, client_id: str, is_expensive: bool = False) -> Tuple[bool, Optional[SecurityViolation]]:
        """Check rate limits for client."""
        current_time = time.time()
        window_start = current_time - self.config.rate_limit_window_seconds
        
        with self._lock:
            # Clean old entries
            client_requests = self.rate_limiter[client_id]
            while client_requests and client_requests[0] < window_start:
                client_requests.popleft()
            
            # Check regular rate limit
            if len(client_requests) >= self.config.max_requests_per_window:
                violation = SecurityViolation(
                    attack_type=AttackType.RATE_LIMIT_EXCEEDED,
                    severity='medium',
                    description=f'Rate limit exceeded: {len(client_requests)} requests in window',
                    client_identifier=client_id
                )
                return False, violation
            
            # Check expensive operations limit
            if is_expensive:
                expensive_requests = self.expensive_operations[client_id]
                while expensive_requests and expensive_requests[0] < window_start:
                    expensive_requests.popleft()
                
                if len(expensive_requests) >= self.config.max_expensive_operations_per_window:
                    violation = SecurityViolation(
                        attack_type=AttackType.RATE_LIMIT_EXCEEDED,
                        severity='high',
                        description=f'Expensive operations limit exceeded: {len(expensive_requests)} in window',
                        client_identifier=client_id
                    )
                    return False, violation
                
                expensive_requests.append(current_time)
            
            # Record request
            client_requests.append(current_time)
            
        return True, None
    
    def start_execution_timer(self) -> float:
        """Start execution timer and return start time."""
        return time.time()
    
    def check_execution_time(self, start_time: float, client_id: Optional[str] = None) -> Tuple[bool, Optional[SecurityViolation]]:
        """Check if execution time exceeds limits."""
        elapsed = time.time() - start_time
        
        if elapsed > self.config.max_execution_time_seconds:
            violation = SecurityViolation(
                attack_type=AttackType.RESOURCE_EXHAUSTION,
                severity='high',
                description=f'Execution time {elapsed:.2f}s exceeds limit {self.config.max_execution_time_seconds}s',
                client_identifier=client_id
            )
            return False, violation
            
        return True, None
    
    def check_result_size(self, result_size: int, client_id: Optional[str] = None) -> Tuple[bool, Optional[SecurityViolation]]:
        """Check if result size exceeds limits."""
        if result_size > self.config.max_result_size_bytes:
            violation = SecurityViolation(
                attack_type=AttackType.RESOURCE_EXHAUSTION,
                severity='medium',
                description=f'Result size {result_size} exceeds limit {self.config.max_result_size_bytes}',
                client_identifier=client_id
            )
            return False, violation
            
        return True, None
    
    def estimate_query_complexity(self, query: str) -> int:
        """Estimate query complexity score."""
        score = 0
        query_lower = query.lower()
        
        # Base score for any query
        score += 2
        
        # JOIN operations = 10 points each
        score += len(re.findall(r'\bjoin\b', query_lower)) * 10
        
        # LIKE operations = 5 points each  
        score += len(re.findall(r'\blike\b', query_lower)) * 5
        
        # Subqueries = 15 points each
        score += query_lower.count('(select') * 15
        
        # UNION operations = 20 points each
        score += len(re.findall(r'\bunion\b', query_lower)) * 20
        
        # Function calls = 2 points each
        score += len(re.findall(r'\w+\s*\(', query)) * 2
        
        # ORDER BY = 3 points
        if 'order by' in query_lower:
            score += 3
            
        # GROUP BY = 5 points  
        if 'group by' in query_lower:
            score += 5
            
        # HAVING = 8 points
        if 'having' in query_lower:
            score += 8
            
        return score


def create_secure_validators(config: Optional[SecurityConfig] = None) -> Tuple[SQLSecurityValidator, ProtocolMessageValidator, ResourceProtection]:
    """
    Factory function to create all security validators with shared configuration.
    
    Args:
        config: Optional security configuration
        
    Returns:
        Tuple of (sql_validator, protocol_validator, resource_protector)
    """
    if config is None:
        config = SecurityConfig()
        
    sql_validator = SQLSecurityValidator(config)
    protocol_validator = ProtocolMessageValidator(config)
    resource_protector = ResourceProtection(config)
    
    return sql_validator, protocol_validator, resource_protector


def sanitize_sql_query(query: str) -> str:
    """
    Sanitize SQL query by removing dangerous elements.
    
    Args:
        query: Raw SQL query
        
    Returns:
        Sanitized SQL query
    """
    # Remove comments
    sanitized = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
    sanitized = re.sub(r'/\*.*?\*/', '', sanitized, flags=re.DOTALL)
    
    # Normalize whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized)
    sanitized = sanitized.strip()
    
    return sanitized


def sanitize_table_name(table_name: str) -> str:
    """
    Sanitize table name to only allow safe characters.
    
    Args:
        table_name: Raw table name
        
    Returns:
        Sanitized table name
    """
    # Only allow alphanumeric characters and underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', table_name)
    
    # Ensure it starts with letter or underscore
    if sanitized and not re.match(r'^[a-zA-Z_]', sanitized):
        sanitized = '_' + sanitized
        
    return sanitized


def create_client_identifier_hash(client_info: Dict[str, Any]) -> str:
    """
    Create a secure hash-based client identifier.
    
    Args:
        client_info: Dictionary with client information
        
    Returns:
        Secure client identifier hash
    """
    # Create deterministic hash from client info
    info_str = '|'.join(f"{k}:{v}" for k, v in sorted(client_info.items()))
    return hashlib.sha256(info_str.encode()).hexdigest()[:32]


# Example usage and integration points
if __name__ == "__main__":
    # Example usage
    config = SecurityConfig()
    sql_validator, protocol_validator, resource_protector = create_secure_validators(config)
    
    # Test SQL validation
    test_query = "SELECT * FROM users WHERE id = 1"
    is_valid, violations = sql_validator.validate_query(test_query, "test_client")
    print(f"SQL validation result: {is_valid}, violations: {len(violations)}")
    
    # Test protocol validation
    is_valid, violations = protocol_validator.validate_table_name("users", "test_client")
    print(f"Table name validation result: {is_valid}, violations: {len(violations)}")
    
    # Test rate limiting
    is_allowed, violation = resource_protector.check_rate_limit("test_client")
    print(f"Rate limit check: {is_allowed}")