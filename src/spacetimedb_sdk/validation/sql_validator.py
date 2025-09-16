"""
SQL validation to prevent injection attacks and ensure query safety.

This module provides comprehensive SQL validation for SpacetimeDB queries,
preventing SQL injection attacks and ensuring query safety.
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from .validators import Validator, ValidationResult, ValidationError, ValidationConfig
from .timeout_cache_utils import (
    with_timeout_and_cache, 
    with_timeout, 
    ValidationTimeoutError,
    TimeoutValidator
)


class SQLValidationError(ValidationError):
    """Specific error for SQL validation failures."""
    pass


class SQLValidator(Validator, TimeoutValidator):
    """
    Validator for SQL queries to prevent injection attacks.
    
    This validator:
    - Detects and prevents SQL injection attempts
    - Validates query structure and syntax
    - Enforces parameterized queries
    - Blocks dangerous SQL keywords
    - Limits query length and complexity
    - Sanitizes string literals
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        timeout_seconds = config.validation_timeout if config else 5.0
        # Initialize parent classes - Validator first, then TimeoutValidator
        Validator.__init__(self, config)
        TimeoutValidator.__init__(self, timeout_seconds)
        
        # Initialize regex compilation cache
        self._compiled_patterns = {}
        
        # Patterns for detecting SQL injection attempts (compiled with caching)
        self._injection_pattern_strings = [
            # Comment injection
            (r'--', re.IGNORECASE, 'comment_dashes'),
            (r'/\*.*?\*/', re.IGNORECASE | re.DOTALL, 'comment_blocks'),
            
            # String escape attempts
            (r"'.*?'.*?'", re.IGNORECASE, 'string_escapes_single'),
            (r'".*?".*?"', re.IGNORECASE, 'string_escapes_double'),
            
            # Union-based injection
            (r'\bunion\b.*?\bselect\b', re.IGNORECASE, 'union_select'),
            
            # Boolean-based injection
            (r'\bor\b\s+\d+\s*=\s*\d+', re.IGNORECASE, 'boolean_or_numeric'),
            (r'\band\b\s+\d+\s*=\s*\d+', re.IGNORECASE, 'boolean_and_numeric'),
            (r'\bor\b\s+\w+\s*=\s*\w+', re.IGNORECASE, 'boolean_or_alpha'),
            (r'\band\b\s+\w+\s*=\s*\w+', re.IGNORECASE, 'boolean_and_alpha'),
            
            # Time-based injection
            (r'\bsleep\s*\(', re.IGNORECASE, 'time_sleep'),
            (r'\bwaitfor\b.*?\bdelay\b', re.IGNORECASE, 'time_waitfor'),
            (r'\bbenchmark\s*\(', re.IGNORECASE, 'time_benchmark'),
            
            # Stacked queries
            (r';\s*(?:select|insert|update|delete|drop|create|alter)', re.IGNORECASE, 'stacked_queries'),
            
            # System function calls
            (r'\bload_file\s*\(', re.IGNORECASE, 'system_load_file'),
            (r'\binto\s+outfile\b', re.IGNORECASE, 'system_outfile'),
            (r'\bexec\s*\(', re.IGNORECASE, 'system_exec'),
            
            # Hex encoding attempts
            (r'0x[0-9a-f]+', re.IGNORECASE, 'hex_encoding'),
            
            # Char function abuse
            (r'\bchar\s*\(', re.IGNORECASE, 'char_function'),
            (r'\bascii\s*\(', re.IGNORECASE, 'ascii_function'),
        ]
        
        # Compile patterns with caching
        self._injection_patterns = self._get_compiled_patterns()
        
        # Dangerous SQL keywords that should be blocked
        self._dangerous_keywords = {
            'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'GRANT', 'REVOKE',
            'INSERT', 'UPDATE', 'EXEC', 'EXECUTE', 'BULK', 'SHUTDOWN', 'DBCC',
            'BACKUP', 'RESTORE', 'KILL', 'LOAD', 'DUMP', 'RENAME', 'REPLACE'
        }
        
        # Add custom blocked keywords from config
        if self.config.blocked_sql_keywords:
            self._dangerous_keywords.update(kw.upper() for kw in self.config.blocked_sql_keywords)
        
        # Pattern for detecting parameterized queries (compiled with caching)
        self._parameter_pattern = self._get_compiled_pattern(
            r'(?:\?|\$\d+|:\w+)', re.IGNORECASE, 'parameter_pattern'
        )
    
    def _get_compiled_pattern(self, pattern: str, flags: int, pattern_id: str):
        """Get a compiled regex pattern with caching."""
        cache_key = f"{pattern_id}_{hash(pattern)}_{flags}"
        
        if cache_key not in self._compiled_patterns:
            try:
                self._compiled_patterns[cache_key] = re.compile(pattern, flags)
            except re.error as e:
                raise SQLValidationError(f"Invalid regex pattern {pattern_id}: {e}")
        
        return self._compiled_patterns[cache_key]
    
    def _get_compiled_patterns(self):
        """Get all compiled injection patterns with caching."""
        patterns = []
        for pattern_str, flags, pattern_id in self._injection_pattern_strings:
            compiled_pattern = self._get_compiled_pattern(pattern_str, flags, pattern_id)
            patterns.append(compiled_pattern)
        return patterns
    
    @with_timeout_and_cache(timeout_seconds=5.0, cache_ttl_seconds=300.0)
    def validate(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """
        Validate SQL query for injection attempts.
        
        Args:
            value: SQL query string to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with validation status and sanitized query
        """
        errors = []
        warnings = []
        
        # Type check
        if not isinstance(value, str):
            errors.append(SQLValidationError(
                f"SQL query must be a string, got {type(value).__name__}",
                field=field,
                value=value
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Length check
        if len(value) > self.config.max_query_length:
            errors.append(SQLValidationError(
                f"SQL query too long: {len(value)} > {self.config.max_query_length}",
                field=field,
                value=value
            ))
        
        # Empty query check
        if not value.strip():
            errors.append(SQLValidationError(
                "SQL query cannot be empty",
                field=field,
                value=value
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Check for injection patterns with timeout protection
        try:
            injection_errors = self._with_timeout(
                self._check_injection_patterns, value, field
            )
            errors.extend(injection_errors)
        except ValidationTimeoutError as e:
            errors.append(SQLValidationError(
                f"SQL injection pattern check timed out: {e}",
                field=field,
                value=value
            ))
        
        # Check for dangerous keywords
        keyword_errors = self._check_dangerous_keywords(value, field)
        errors.extend(keyword_errors)
        
        # Check for multiple statements
        if not self.config.allow_multi_statements:
            multi_statement_errors = self._check_multi_statements(value, field)
            errors.extend(multi_statement_errors)
        
        # Validate parameterization
        param_warnings = self._validate_parameterization(value, field)
        warnings.extend(param_warnings)
        
        # Sanitize the query
        sanitized_query = self._sanitize_query(value) if not errors else None
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            sanitized_value=sanitized_query,
            errors=errors,
            warnings=warnings
        )
    
    @with_timeout_and_cache(timeout_seconds=3.0, cache_ttl_seconds=600.0)
    def _check_injection_patterns(self, query: str, field: Optional[str]) -> List[SQLValidationError]:
        """Check for SQL injection patterns with caching and timeout protection."""
        errors = []
        
        # Process patterns in batches to allow timeout interruption
        batch_size = 5
        for i in range(0, len(self._injection_patterns), batch_size):
            batch = self._injection_patterns[i:i + batch_size]
            
            for pattern in batch:
                try:
                    if pattern.search(query):
                        errors.append(SQLValidationError(
                            f"SQL injection pattern detected: {pattern.pattern}",
                            field=field,
                            value=query
                        ))
                except re.error as e:
                    # Log regex execution error but continue with other patterns
                    self.logger.warning(f"Regex pattern failed: {pattern.pattern}, error: {e}")
                    continue
        
        return errors
    
    @with_timeout_and_cache(timeout_seconds=2.0, cache_ttl_seconds=600.0)
    def _check_dangerous_keywords(self, query: str, field: Optional[str]) -> List[SQLValidationError]:
        """Check for dangerous SQL keywords with caching."""
        errors = []
        
        # Split query into tokens (with timeout protection for large queries)
        try:
            tokens = re.findall(r'\b\w+\b', query.upper())
            
            # Limit token processing to prevent DoS
            if len(tokens) > 1000:
                errors.append(SQLValidationError(
                    f"Query has too many tokens: {len(tokens)} > 1000",
                    field=field,
                    value=query
                ))
                return errors
            
            for token in tokens:
                if token in self._dangerous_keywords:
                    errors.append(SQLValidationError(
                        f"Dangerous SQL keyword detected: {token}",
                        field=field,
                        value=query
                    ))
                    
        except re.error as e:
            errors.append(SQLValidationError(
                f"Failed to tokenize query: {e}",
                field=field,
                value=query
            ))
        
        return errors
    
    def _check_multi_statements(self, query: str, field: Optional[str]) -> List[SQLValidationError]:
        """Check for multiple statements."""
        errors = []
        
        # Remove string literals to avoid false positives
        query_without_strings = re.sub(r"'[^']*'", "''", query)
        query_without_strings = re.sub(r'"[^"]*"', '""', query_without_strings)
        
        # Count semicolons (statement separators)
        semicolons = query_without_strings.count(';')
        
        # Allow one trailing semicolon
        if semicolons > 1 or (semicolons == 1 and not query_without_strings.rstrip().endswith(';')):
            errors.append(SQLValidationError(
                "Multiple SQL statements not allowed",
                field=field,
                value=query
            ))
        
        return errors
    
    def _validate_parameterization(self, query: str, field: Optional[str]) -> List[str]:
        """Validate that query uses parameterized queries."""
        warnings = []
        
        # Check if query contains parameters
        has_parameters = bool(self._parameter_pattern.search(query))
        
        # Check if query contains potential user input (single quotes)
        has_quotes = "'" in query
        
        if has_quotes and not has_parameters:
            warnings.append(
                "Query contains string literals but no parameters. Consider using parameterized queries."
            )
        
        return warnings
    
    def _sanitize_query(self, query: str) -> str:
        """Sanitize SQL query by removing dangerous elements."""
        # Remove comments
        sanitized = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
        sanitized = re.sub(r'/\*.*?\*/', '', sanitized, flags=re.DOTALL)
        
        # Normalize whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized)
        sanitized = sanitized.strip()
        
        return sanitized
    
    def validate_select_query(self, query: str, field: Optional[str] = None) -> ValidationResult:
        """
        Validate a SELECT query specifically.
        
        Args:
            query: SELECT query to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with SELECT-specific validation
        """
        result = self.validate(query, field)
        
        if not result.is_valid:
            return result
        
        # Additional SELECT-specific validation
        query_upper = query.upper().strip()
        
        if not query_upper.startswith('SELECT'):
            error = SQLValidationError(
                "Query must start with SELECT",
                field=field,
                value=query
            )
            return ValidationResult(is_valid=False, errors=[error])
        
        return result
    
    def create_parameterized_query(self, query_template: str, params: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """
        Create a parameterized query from template and parameters.
        
        Args:
            query_template: Query template with named parameters (:param)
            params: Dictionary of parameter values
            
        Returns:
            Tuple of (query, param_list) for safe execution
        """
        # Validate the template
        template_result = self.validate(query_template, "query_template")
        if not template_result.is_valid:
            raise SQLValidationError(
                f"Invalid query template: {'; '.join(str(e) for e in template_result.errors)}"
            )
        
        # Extract parameter names from template
        param_names = re.findall(r':(\w+)', query_template)
        
        # Validate that all parameters are provided
        missing_params = set(param_names) - set(params.keys())
        if missing_params:
            raise SQLValidationError(f"Missing parameters: {missing_params}")
        
        # Build parameter list in order
        param_list = []
        query = query_template
        
        for param_name in param_names:
            if param_name in params:
                param_list.append(params[param_name])
                # Replace named parameter with positional parameter
                query = query.replace(f':{param_name}', '?', 1)
        
        return query, param_list
    
    def validate_parameter_value(self, value: Any, param_name: str) -> ValidationResult:
        """
        Validate a parameter value for use in parameterized queries.
        
        Args:
            value: Parameter value to validate
            param_name: Name of the parameter
            
        Returns:
            ValidationResult with parameter validation
        """
        errors = []
        warnings = []
        
        # Check for None values
        if value is None:
            return ValidationResult(is_valid=True, sanitized_value=None)
        
        # Check for basic types
        if isinstance(value, (str, int, float, bool, bytes)):
            # String length check
            if isinstance(value, str) and len(value) > self.config.max_string_length:
                errors.append(SQLValidationError(
                    f"Parameter '{param_name}' too long: {len(value)} > {self.config.max_string_length}",
                    field=param_name,
                    value=value
                ))
            
            # Check for potential injection in string values
            if isinstance(value, str):
                for pattern in self._injection_patterns[:3]:  # Check only basic patterns
                    if pattern.search(value):
                        warnings.append(
                            f"Parameter '{param_name}' contains potentially dangerous pattern: {pattern.pattern}"
                        )
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                sanitized_value=value,
                errors=errors,
                warnings=warnings
            )
        
        # Check for collections
        if isinstance(value, (list, tuple)):
            if len(value) > self.config.max_array_length:
                errors.append(SQLValidationError(
                    f"Parameter '{param_name}' array too long: {len(value)} > {self.config.max_array_length}",
                    field=param_name,
                    value=value
                ))
            
            # Validate each element
            for i, item in enumerate(value):
                item_result = self.validate_parameter_value(item, f"{param_name}[{i}]")
                if not item_result.is_valid:
                    errors.extend(item_result.errors)
                warnings.extend(item_result.warnings)
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                sanitized_value=value,
                errors=errors,
                warnings=warnings
            )
        
        # Unsupported type
        errors.append(SQLValidationError(
            f"Parameter '{param_name}' has unsupported type: {type(value).__name__}",
            field=param_name,
            value=value
        ))
        
        return ValidationResult(
            is_valid=False,
            sanitized_value=None,
            errors=errors,
            warnings=warnings
        )