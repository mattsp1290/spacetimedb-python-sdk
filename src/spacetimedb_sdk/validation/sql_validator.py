"""
SQL validation to prevent injection attacks and ensure query safety.

This module provides comprehensive SQL validation for SpacetimeDB queries,
preventing SQL injection attacks and ensuring query safety.
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from .validators import Validator, ValidationResult, ValidationError, ValidationConfig


class SQLValidationError(ValidationError):
    """Specific error for SQL validation failures."""
    pass


class SQLValidator(Validator):
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
        super().__init__(config)
        
        # Patterns for detecting SQL injection attempts
        self._injection_patterns = [
            # Comment injection
            re.compile(r'--', re.IGNORECASE),
            re.compile(r'/\*.*?\*/', re.IGNORECASE | re.DOTALL),
            
            # String escape attempts
            re.compile(r"'.*?'.*?'", re.IGNORECASE),
            re.compile(r'".*?".*?"', re.IGNORECASE),
            
            # Union-based injection
            re.compile(r'\bunion\b.*?\bselect\b', re.IGNORECASE),
            
            # Boolean-based injection
            re.compile(r'\bor\b\s+\d+\s*=\s*\d+', re.IGNORECASE),
            re.compile(r'\band\b\s+\d+\s*=\s*\d+', re.IGNORECASE),
            re.compile(r'\bor\b\s+\w+\s*=\s*\w+', re.IGNORECASE),
            re.compile(r'\band\b\s+\w+\s*=\s*\w+', re.IGNORECASE),
            
            # Time-based injection
            re.compile(r'\bsleep\s*\(', re.IGNORECASE),
            re.compile(r'\bwaitfor\b.*?\bdelay\b', re.IGNORECASE),
            re.compile(r'\bbenchmark\s*\(', re.IGNORECASE),
            
            # Stacked queries
            re.compile(r';\s*(?:select|insert|update|delete|drop|create|alter)', re.IGNORECASE),
            
            # System function calls
            re.compile(r'\bload_file\s*\(', re.IGNORECASE),
            re.compile(r'\binto\s+outfile\b', re.IGNORECASE),
            re.compile(r'\bexec\s*\(', re.IGNORECASE),
            
            # Hex encoding attempts
            re.compile(r'0x[0-9a-f]+', re.IGNORECASE),
            
            # Char function abuse
            re.compile(r'\bchar\s*\(', re.IGNORECASE),
            re.compile(r'\bascii\s*\(', re.IGNORECASE),
        ]
        
        # Dangerous SQL keywords that should be blocked
        self._dangerous_keywords = {
            'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'GRANT', 'REVOKE',
            'INSERT', 'UPDATE', 'EXEC', 'EXECUTE', 'BULK', 'SHUTDOWN', 'DBCC',
            'BACKUP', 'RESTORE', 'KILL', 'LOAD', 'DUMP', 'RENAME', 'REPLACE'
        }
        
        # Add custom blocked keywords from config
        if self.config.blocked_sql_keywords:
            self._dangerous_keywords.update(kw.upper() for kw in self.config.blocked_sql_keywords)
        
        # Pattern for detecting parameterized queries
        self._parameter_pattern = re.compile(r'(?:\?|\$\d+|:\w+)', re.IGNORECASE)
    
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
        
        # Check for injection patterns
        injection_errors = self._check_injection_patterns(value, field)
        errors.extend(injection_errors)
        
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
    
    def _check_injection_patterns(self, query: str, field: Optional[str]) -> List[SQLValidationError]:
        """Check for SQL injection patterns."""
        errors = []
        
        for pattern in self._injection_patterns:
            if pattern.search(query):
                errors.append(SQLValidationError(
                    f"SQL injection pattern detected: {pattern.pattern}",
                    field=field,
                    value=query
                ))
        
        return errors
    
    def _check_dangerous_keywords(self, query: str, field: Optional[str]) -> List[SQLValidationError]:
        """Check for dangerous SQL keywords."""
        errors = []
        
        # Split query into tokens
        tokens = re.findall(r'\b\w+\b', query.upper())
        
        for token in tokens:
            if token in self._dangerous_keywords:
                errors.append(SQLValidationError(
                    f"Dangerous SQL keyword detected: {token}",
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
        
        # Find all parameter occurrences outside of string literals and comments
        param_pattern = re.compile(r':(\w+)')
        param_list = []
        result_query = []
        i = 0
        
        while i < len(query_template):
            char = query_template[i]
            
            # Skip string literals (single and double quotes)
            if char in ("'", '"'):
                quote_char = char
                result_query.append(char)
                i += 1
                while i < len(query_template):
                    current_char = query_template[i]
                    result_query.append(current_char)
                    if current_char == quote_char:
                        # Check if it's escaped
                        if i == 0 or query_template[i-1] != '\\':
                            break
                    i += 1
                i += 1
                continue
            
            # Skip line comments (-- style)
            if char == '-' and i + 1 < len(query_template) and query_template[i + 1] == '-':
                result_query.append(char)
                i += 1
                while i < len(query_template) and query_template[i] != '\n':
                    result_query.append(query_template[i])
                    i += 1
                continue
            
            # Skip block comments (/* */ style)
            if char == '/' and i + 1 < len(query_template) and query_template[i + 1] == '*':
                result_query.append(char)
                i += 1
                result_query.append(query_template[i])  # append the '*'
                i += 1
                while i + 1 < len(query_template):
                    result_query.append(query_template[i])
                    if query_template[i] == '*' and query_template[i + 1] == '/':
                        i += 1
                        result_query.append(query_template[i])  # append the '/'
                        break
                    i += 1
                i += 1
                continue
            
            # Check for parameter pattern
            if char == ':':
                match = param_pattern.match(query_template, i)
                if match:
                    param_name = match.group(1)
                    
                    # Validate that the parameter is provided
                    if param_name not in params:
                        raise SQLValidationError(f"Missing parameter: {param_name}")
                    
                    # Add parameter value to list and replace with placeholder
                    param_list.append(params[param_name])
                    result_query.append('?')
                    i = match.end()
                    continue
            
            # Regular character
            result_query.append(char)
            i += 1
        
        # Validate that all provided parameters are used
        used_params = set()
        for match in param_pattern.finditer(self._remove_literals_and_comments(query_template)):
            used_params.add(match.group(1))
        
        unused_params = set(params.keys()) - used_params
        if unused_params:
            raise SQLValidationError(f"Unused parameters: {unused_params}")
        
        return ''.join(result_query), param_list
    
    def _remove_literals_and_comments(self, query: str) -> str:
        """Helper method to remove string literals and comments for parameter validation."""
        result = []
        i = 0
        
        while i < len(query):
            char = query[i]
            
            # Skip string literals
            if char in ("'", '"'):
                quote_char = char
                i += 1
                while i < len(query):
                    if query[i] == quote_char and (i == 0 or query[i-1] != '\\'):
                        break
                    i += 1
                i += 1
                continue
            
            # Skip line comments
            if char == '-' and i + 1 < len(query) and query[i + 1] == '-':
                while i < len(query) and query[i] != '\n':
                    i += 1
                continue
            
            # Skip block comments
            if char == '/' and i + 1 < len(query) and query[i + 1] == '*':
                i += 2
                while i + 1 < len(query):
                    if query[i] == '*' and query[i + 1] == '/':
                        i += 2
                        break
                    i += 1
                continue
            
            result.append(char)
            i += 1
        
        return ''.join(result)
    
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