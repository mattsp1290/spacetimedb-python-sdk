"""
Data validation to prevent memory exhaustion and ensure data integrity.

This module provides comprehensive data validation for JSON parsing,
data structures, and general data size limits to prevent DoS attacks
and ensure system stability.
"""

import json
import sys
from typing import Any, Optional, List, Dict, Union
from .validators import Validator, ValidationResult, ValidationError, ValidationConfig


class JSONValidationError(ValidationError):
    """Specific error for JSON validation failures."""
    pass


class DataSizeValidationError(ValidationError):
    """Specific error for data size validation failures."""
    pass


class JSONValidator(Validator):
    """
    Validator for JSON data to prevent memory exhaustion and ensure safety.
    
    This validator:
    - Limits JSON size to prevent memory exhaustion
    - Limits nesting depth to prevent stack overflow
    - Validates JSON structure and syntax
    - Prevents billion laughs attacks
    - Sanitizes potentially dangerous content
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        super().__init__(config)
    
    def validate(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """
        Validate JSON data for safety and size limits.
        
        Args:
            value: JSON string or data structure to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with validation status and parsed JSON
        """
        errors = []
        warnings = []
        
        # Handle string input (JSON to be parsed)
        if isinstance(value, str):
            return self._validate_json_string(value, field)
        
        # Handle already parsed JSON data
        return self._validate_json_data(value, field)
    
    def _validate_json_string(self, json_str: str, field: Optional[str]) -> ValidationResult:
        """Validate JSON string before parsing."""
        errors = []
        warnings = []
        
        # Size check
        if len(json_str) > self.config.max_json_size:
            errors.append(JSONValidationError(
                f"JSON string too large: {len(json_str)} > {self.config.max_json_size}",
                field=field,
                value=json_str
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Empty check
        if not json_str.strip():
            errors.append(JSONValidationError(
                "JSON string cannot be empty",
                field=field,
                value=json_str
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Check for potential billion laughs attack
        if self._detect_billion_laughs(json_str):
            errors.append(JSONValidationError(
                "Potential billion laughs attack detected",
                field=field,
                value=json_str
            ))
        
        # Pre-scan for depth before parsing to prevent memory exhaustion
        try:
            pre_scan_depth = self._pre_scan_depth(json_str)
            if pre_scan_depth > self.config.max_json_depth:
                errors.append(JSONValidationError(
                    f"JSON nesting too deep: {pre_scan_depth} > {self.config.max_json_depth}",
                    field=field,
                    value=json_str
                ))
                return ValidationResult(is_valid=False, errors=errors)
        except Exception as e:
            errors.append(JSONValidationError(
                f"JSON depth pre-scan failed: {e}",
                field=field,
                value=json_str
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Try to parse JSON
        try:
            parsed_data = json.loads(json_str)
        
        except json.JSONDecodeError as e:
            errors.append(JSONValidationError(
                f"Invalid JSON: {e}",
                field=field,
                value=json_str
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        except RecursionError:
            errors.append(JSONValidationError(
                "JSON nesting too deep (recursion limit exceeded)",
                field=field,
                value=json_str
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        except Exception as e:
            errors.append(JSONValidationError(
                f"JSON parsing failed: {e}",
                field=field,
                value=json_str
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # Validate the parsed data
        data_result = self._validate_json_data(parsed_data, field)
        
        return ValidationResult(
            is_valid=data_result.is_valid,
            sanitized_value=data_result.sanitized_value,
            errors=data_result.errors,
            warnings=warnings + data_result.warnings
        )
    
    def _validate_json_data(self, data: Any, field: Optional[str]) -> ValidationResult:
        """Validate already parsed JSON data."""
        errors = []
        warnings = []
        
        # Validate data structure
        try:
            self._validate_data_structure(data, field, depth=0)
        except ValidationError as e:
            errors.append(e)
        
        # Calculate approximate size
        size_estimate = self._estimate_size(data)
        if size_estimate > self.config.max_json_size:
            warnings.append(
                f"JSON data size estimate ({size_estimate} bytes) exceeds limit ({self.config.max_json_size} bytes)"
            )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            sanitized_value=data if len(errors) == 0 else None,
            errors=errors,
            warnings=warnings
        )
    

    
    def _pre_scan_depth(self, json_str: str) -> int:
        """
        Pre-scan JSON string to detect excessive nesting before parsing.
        This prevents memory exhaustion from deeply nested structures.
        """
        max_depth = 0
        current_depth = 0
        in_string = False
        escaped = False
        
        for i, char in enumerate(json_str):
            if escaped:
                escaped = False
                continue
            
            if char == '\\' and in_string:
                escaped = True
                continue
            
            if char == '"' and not escaped:
                in_string = not in_string
                continue
            
            if in_string:
                continue
            
            if char in '{[':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
                
                # Fail fast if depth exceeds limit
                if current_depth > self.config.max_json_depth:
                    return current_depth
            elif char in '}]':
                current_depth = max(0, current_depth - 1)
        
        return max_depth
    
    def _validate_data_structure(self, data: Any, field: Optional[str], depth: int = 0):
        """Recursively validate data structure."""
        # Check depth
        if depth > self.config.max_json_depth:
            raise JSONValidationError(
                f"Data nesting too deep: {depth} > {self.config.max_json_depth}",
                field=field,
                value=data
            )
        
        # Validate based on type
        if isinstance(data, dict):
            self._validate_dict(data, field, depth)
        elif isinstance(data, list):
            self._validate_list(data, field, depth)
        elif isinstance(data, str):
            self._validate_string(data, field)
        # Other types (int, float, bool, None) are safe
    
    def _validate_dict(self, data: Dict[str, Any], field: Optional[str], depth: int):
        """Validate dictionary structure."""
        # Check number of keys
        if len(data) > self.config.max_object_keys:
            raise JSONValidationError(
                f"Too many object keys: {len(data)} > {self.config.max_object_keys}",
                field=field,
                value=data
            )
        
        # Validate each key-value pair
        for key, value in data.items():
            # Validate key
            if not isinstance(key, str):
                raise JSONValidationError(
                    f"Object key must be string, got {type(key).__name__}",
                    field=field,
                    value=data
                )
            
            if len(key) > 1000:  # Reasonable key length limit
                raise JSONValidationError(
                    f"Object key too long: {len(key)} > 1000",
                    field=field,
                    value=data
                )
            
            # Recursively validate value
            self._validate_data_structure(value, f"{field}.{key}" if field else key, depth + 1)
    
    def _validate_list(self, data: List[Any], field: Optional[str], depth: int):
        """Validate list structure."""
        # Check array length
        if len(data) > self.config.max_array_length:
            raise JSONValidationError(
                f"Array too long: {len(data)} > {self.config.max_array_length}",
                field=field,
                value=data
            )
        
        # Validate each element
        for i, item in enumerate(data):
            self._validate_data_structure(item, f"{field}[{i}]" if field else f"[{i}]", depth + 1)
    
    def _validate_string(self, data: str, field: Optional[str]):
        """Validate string value."""
        if len(data) > self.config.max_string_length:
            raise JSONValidationError(
                f"String too long: {len(data)} > {self.config.max_string_length}",
                field=field,
                value=data
            )
    
    def _detect_billion_laughs(self, json_str: str) -> bool:
        """Detect potential billion laughs attack patterns."""
        # Check for excessive repetition of characters
        for char in ['{', '[', '"', '}', ']']:
            if json_str.count(char) > 10000:
                return True
        
        # Check for very long strings of repeated characters
        import re
        if re.search(r'(.)\1{10000,}', json_str):
            return True
        
        return False
    
    def _estimate_size(self, data: Any) -> int:
        """Estimate memory size of data structure."""
        if data is None:
            return 4  # None reference
        elif isinstance(data, bool):
            return 4  # Boolean
        elif isinstance(data, int):
            return 8  # Integer
        elif isinstance(data, float):
            return 8  # Float
        elif isinstance(data, str):
            return len(data.encode('utf-8'))
        elif isinstance(data, dict):
            size = 40  # Dict overhead
            for key, value in data.items():
                size += self._estimate_size(key)
                size += self._estimate_size(value)
            return size
        elif isinstance(data, list):
            size = 40  # List overhead
            for item in data:
                size += self._estimate_size(item)
            return size
        else:
            return 100  # Unknown type estimate


class DataSizeValidator(Validator):
    """
    Validator for general data size limits to prevent DoS attacks.
    
    This validator enforces size limits on various data types to prevent
    memory exhaustion and other resource-based attacks.
    """
    
    def validate(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """
        Validate data size limits.
        
        Args:
            value: Data to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with size validation
        """
        errors = []
        warnings = []
        
        # Validate based on type
        if isinstance(value, str):
            errors.extend(self._validate_string_size(value, field))
        elif isinstance(value, bytes):
            errors.extend(self._validate_bytes_size(value, field))
        elif isinstance(value, (list, tuple)):
            errors.extend(self._validate_array_size(value, field))
        elif isinstance(value, dict):
            errors.extend(self._validate_dict_size(value, field))
        elif hasattr(value, '__len__'):
            # Generic sequence validation
            errors.extend(self._validate_sequence_size(value, field))
        
        # Check system memory usage
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > 90:
                warnings.append(f"High memory usage detected: {memory_percent}%")
        except ImportError:
            pass  # psutil not available
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            sanitized_value=value if len(errors) == 0 else None,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_string_size(self, value: str, field: Optional[str]) -> List[DataSizeValidationError]:
        """Validate string size."""
        errors = []
        
        if len(value) > self.config.max_string_length:
            errors.append(DataSizeValidationError(
                f"String too long: {len(value)} > {self.config.max_string_length}",
                field=field,
                value=value
            ))
        
        return errors
    
    def _validate_bytes_size(self, value: bytes, field: Optional[str]) -> List[DataSizeValidationError]:
        """Validate bytes size."""
        errors = []
        
        if len(value) > self.config.max_string_length:  # Reuse string limit for bytes
            errors.append(DataSizeValidationError(
                f"Bytes too long: {len(value)} > {self.config.max_string_length}",
                field=field,
                value=value
            ))
        
        return errors
    
    def _validate_array_size(self, value: Union[list, tuple], field: Optional[str]) -> List[DataSizeValidationError]:
        """Validate array size."""
        errors = []
        
        if len(value) > self.config.max_array_length:
            errors.append(DataSizeValidationError(
                f"Array too long: {len(value)} > {self.config.max_array_length}",
                field=field,
                value=value
            ))
        
        return errors
    
    def _validate_dict_size(self, value: dict, field: Optional[str]) -> List[DataSizeValidationError]:
        """Validate dictionary size."""
        errors = []
        
        if len(value) > self.config.max_object_keys:
            errors.append(DataSizeValidationError(
                f"Dictionary too many keys: {len(value)} > {self.config.max_object_keys}",
                field=field,
                value=value
            ))
        
        return errors
    
    def _validate_sequence_size(self, value: Any, field: Optional[str]) -> List[DataSizeValidationError]:
        """Validate generic sequence size."""
        errors = []
        
        try:
            length = len(value)
            if length > self.config.max_array_length:
                errors.append(DataSizeValidationError(
                    f"Sequence too long: {length} > {self.config.max_array_length}",
                    field=field,
                    value=value
                ))
        except Exception:
            pass  # Can't get length
        
        return errors


class MessageValidator(Validator):
    """
    Validator for SpacetimeDB messages to ensure they meet protocol requirements.
    
    This validator combines JSON validation with message-specific validation
    to ensure messages are safe and properly formatted.
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        super().__init__(config)
        self.json_validator = JSONValidator(config)
        self.size_validator = DataSizeValidator(config)
    
    def validate(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """
        Validate SpacetimeDB message.
        
        Args:
            value: Message to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with message validation
        """
        errors = []
        warnings = []
        
        # First validate as JSON data
        json_result = self.json_validator.validate(value, field)
        errors.extend(json_result.errors)
        warnings.extend(json_result.warnings)
        
        if not json_result.is_valid:
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Then validate size constraints
        size_result = self.size_validator.validate(json_result.sanitized_value, field)
        errors.extend(size_result.errors)
        warnings.extend(size_result.warnings)
        
        # Message-specific validation
        if isinstance(json_result.sanitized_value, dict):
            message_errors = self._validate_message_structure(json_result.sanitized_value, field)
            errors.extend(message_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            sanitized_value=json_result.sanitized_value if len(errors) == 0 else None,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_message_structure(self, message: Dict[str, Any], field: Optional[str]) -> List[ValidationError]:
        """Validate SpacetimeDB message structure."""
        errors = []
        
        # Check for required fields based on message type
        if not isinstance(message, dict):
            errors.append(ValidationError(
                "Message must be a dictionary",
                field=field,
                value=message
            ))
            return errors
        
        # Validate message ID if present
        if 'message_id' in message:
            msg_id = message['message_id']
            if not isinstance(msg_id, (str, bytes)):
                errors.append(ValidationError(
                    "Message ID must be string or bytes",
                    field=f"{field}.message_id" if field else "message_id",
                    value=msg_id
                ))
        
        # Validate timestamp if present
        if 'timestamp' in message:
            timestamp = message['timestamp']
            if not isinstance(timestamp, (int, float)):
                errors.append(ValidationError(
                    "Timestamp must be numeric",
                    field=f"{field}.timestamp" if field else "timestamp",
                    value=timestamp
                ))
        
        return errors