#!/usr/bin/env python3
"""
Input Validation Example
========================

This example demonstrates comprehensive input validation and sanitization
techniques for secure data handling in SpacetimeDB applications.

Key concepts:
- SQL injection prevention
- XSS protection
- Input sanitization
- Data type validation
- Schema validation
- Rate limiting
- Security headers

Requirements:
- spacetimedb-sdk
- bleach (for HTML sanitization)
- validators
- marshmallow (for schema validation)
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import re
import json
import time
import html
import urllib.parse
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from collections import defaultdict, deque

# Validation libraries
try:
    import bleach
    HAS_BLEACH = True
except ImportError:
    HAS_BLEACH = False
    print("Warning: bleach not installed. HTML sanitization limited.")

try:
    import validators
    HAS_VALIDATORS = True
except ImportError:
    HAS_VALIDATORS = False
    print("Warning: validators not installed. URL validation limited.")

try:
    from marshmallow import Schema, fields, ValidationError, validates, post_load
    HAS_MARSHMALLOW = True
except ImportError:
    HAS_MARSHMALLOW = False
    print("Warning: marshmallow not installed. Schema validation limited.")

from spacetimedb_sdk.validation import DataValidator, SecurityManager


class ValidationError(Exception):
    """Custom validation error"""
    pass


class ValidationLevel(Enum):
    """Validation strictness levels"""
    STRICT = "strict"
    MODERATE = "moderate"
    LENIENT = "lenient"


@dataclass
class ValidationResult:
    """Result of validation operation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_data: Optional[Any] = None
    
    def add_error(self, error: str):
        """Add validation error"""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add validation warning"""
        self.warnings.append(warning)


class InputSanitizer:
    """Comprehensive input sanitization"""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STRICT):
        self.level = level
        self.html_tags_allowed = {
            ValidationLevel.STRICT: [],
            ValidationLevel.MODERATE: ['b', 'i', 'em', 'strong', 'p', 'br'],
            ValidationLevel.LENIENT: ['b', 'i', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li', 'a']
        }
        
        self.html_attributes_allowed = {
            ValidationLevel.STRICT: {},
            ValidationLevel.MODERATE: {},
            ValidationLevel.LENIENT: {'a': ['href', 'title']}
        }
    
    def sanitize_string(self, value: str, max_length: Optional[int] = None) -> ValidationResult:
        """Sanitize string input"""
        
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            result.add_error("Input must be a string")
            return result
        
        # Check length
        if max_length and len(value) > max_length:
            result.add_error(f"String exceeds maximum length of {max_length}")
            return result
        
        # Remove null bytes
        sanitized = value.replace('\x00', '')
        if sanitized != value:
            result.add_warning("Null bytes removed")
        
        # Normalize whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Remove control characters (except tab, newline, carriage return)
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sanitized)
        
        result.sanitized_data = sanitized
        return result
    
    def sanitize_html(self, value: str) -> ValidationResult:
        """Sanitize HTML content"""
        
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            result.add_error("Input must be a string")
            return result
        
        if not HAS_BLEACH:
            # Fallback: escape HTML
            result.sanitized_data = html.escape(value)
            result.add_warning("HTML escaped due to missing bleach library")
            return result
        
        # Get allowed tags and attributes for current level
        allowed_tags = self.html_tags_allowed[self.level]
        allowed_attributes = self.html_attributes_allowed[self.level]
        
        # Clean HTML
        sanitized = bleach.clean(
            value,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
        
        if sanitized != value:
            result.add_warning("HTML content sanitized")
        
        result.sanitized_data = sanitized
        return result
    
    def sanitize_sql_identifier(self, value: str) -> ValidationResult:
        """Sanitize SQL identifier (table name, column name, etc.)"""
        
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            result.add_error("SQL identifier must be a string")
            return result
        
        # SQL identifiers should only contain alphanumeric characters and underscores
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', value):
            result.add_error("SQL identifier contains invalid characters")
            return result
        
        # Check for SQL reserved words
        sql_reserved = {
            'select', 'insert', 'update', 'delete', 'drop', 'create', 'alter',
            'table', 'index', 'view', 'database', 'schema', 'from', 'where',
            'join', 'inner', 'outer', 'left', 'right', 'on', 'group', 'order',
            'by', 'having', 'union', 'distinct', 'as', 'and', 'or', 'not',
            'in', 'exists', 'between', 'like', 'null', 'true', 'false'
        }
        
        if value.lower() in sql_reserved:
            result.add_error(f"'{value}' is a reserved SQL keyword")
            return result
        
        # Length check
        if len(value) > 64:
            result.add_error("SQL identifier too long (max 64 characters)")
            return result
        
        result.sanitized_data = value
        return result
    
    def sanitize_url(self, value: str) -> ValidationResult:
        """Sanitize URL input"""
        
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            result.add_error("URL must be a string")
            return result
        
        # Basic URL validation
        if not re.match(r'^https?://', value):
            result.add_error("URL must start with http:// or https://")
            return result
        
        # Use validators library if available
        if HAS_VALIDATORS:
            if not validators.url(value):
                result.add_error("Invalid URL format")
                return result
        
        # Parse URL components
        try:
            parsed = urllib.parse.urlparse(value)
        except Exception:
            result.add_error("Failed to parse URL")
            return result
        
        # Check for suspicious patterns
        if parsed.hostname:
            # Check for localhost/internal IPs in production
            if parsed.hostname.lower() in ['localhost', '127.0.0.1', '::1']:
                result.add_warning("URL points to localhost")
            
            # Check for private IP ranges
            if self._is_private_ip(parsed.hostname):
                result.add_warning("URL points to private IP address")
        
        # URL encode any suspicious characters
        sanitized = urllib.parse.quote(value, safe=':/?#[]@!$&\'()*+,;=')
        
        result.sanitized_data = sanitized
        return result
    
    def _is_private_ip(self, hostname: str) -> bool:
        """Check if hostname is a private IP address"""
        
        try:
            import ipaddress
            ip = ipaddress.ip_address(hostname)
            return ip.is_private
        except ValueError:
            return False
    
    def sanitize_json(self, value: str, max_depth: int = 10) -> ValidationResult:
        """Sanitize JSON input"""
        
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            result.add_error("JSON must be a string")
            return result
        
        # Parse JSON
        try:
            data = json.loads(value)
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON: {e}")
            return result
        
        # Check depth
        if self._json_depth(data) > max_depth:
            result.add_error(f"JSON depth exceeds maximum of {max_depth}")
            return result
        
        # Sanitize strings in JSON
        sanitized_data = self._sanitize_json_recursive(data)
        
        result.sanitized_data = sanitized_data
        return result
    
    def _json_depth(self, obj: Any, depth: int = 0) -> int:
        """Calculate JSON object depth"""
        
        if isinstance(obj, dict):
            return max([self._json_depth(v, depth + 1) for v in obj.values()] + [depth])
        elif isinstance(obj, list):
            return max([self._json_depth(item, depth + 1) for item in obj] + [depth])
        else:
            return depth
    
    def _sanitize_json_recursive(self, obj: Any) -> Any:
        """Recursively sanitize JSON object"""
        
        if isinstance(obj, dict):
            return {k: self._sanitize_json_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_json_recursive(item) for item in obj]
        elif isinstance(obj, str):
            # Sanitize strings in JSON
            result = self.sanitize_string(obj)
            return result.sanitized_data if result.is_valid else obj
        else:
            return obj


class SchemaValidator:
    """Schema-based validation using marshmallow"""
    
    def __init__(self):
        self.schemas = {}
    
    def register_schema(self, name: str, schema: 'Schema'):
        """Register a validation schema"""
        self.schemas[name] = schema
    
    def validate(self, schema_name: str, data: Dict[str, Any]) -> ValidationResult:
        """Validate data against registered schema"""
        
        result = ValidationResult(is_valid=True)
        
        if schema_name not in self.schemas:
            result.add_error(f"Schema '{schema_name}' not found")
            return result
        
        schema = self.schemas[schema_name]
        
        try:
            validated_data = schema.load(data)
            result.sanitized_data = validated_data
        except ValidationError as e:
            result.is_valid = False
            
            # Extract error messages
            if hasattr(e, 'messages'):
                for field, messages in e.messages.items():
                    if isinstance(messages, list):
                        for msg in messages:
                            result.add_error(f"{field}: {msg}")
                    else:
                        result.add_error(f"{field}: {messages}")
            else:
                result.add_error(str(e))
        
        return result


class RateLimiter:
    """Rate limiting for validation operations"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed"""
        
        current_time = time.time()
        request_times = self.requests[identifier]
        
        # Remove old requests
        while request_times and current_time - request_times[0] > self.window_seconds:
            request_times.popleft()
        
        # Check if under limit
        if len(request_times) >= self.max_requests:
            return False
        
        # Add current request
        request_times.append(current_time)
        return True
    
    def get_remaining_requests(self, identifier: str) -> int:
        """Get remaining requests for identifier"""
        
        current_time = time.time()
        request_times = self.requests[identifier]
        
        # Remove old requests
        while request_times and current_time - request_times[0] > self.window_seconds:
            request_times.popleft()
        
        return max(0, self.max_requests - len(request_times))


def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    """Rate limiting decorator"""
    
    limiter = RateLimiter(max_requests, window_seconds)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use function name as identifier (in real app, use user ID)
            identifier = func.__name__
            
            if not limiter.is_allowed(identifier):
                raise ValidationError(f"Rate limit exceeded for {identifier}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


class InputValidationDemo:
    """Demonstration of input validation techniques"""
    
    def __init__(self):
        self.sanitizer = InputSanitizer(ValidationLevel.STRICT)
        self.schema_validator = SchemaValidator()
        self.rate_limiter = RateLimiter(max_requests=5, window_seconds=10)
        
        # Register schemas
        self._register_schemas()
    
    def _register_schemas(self):
        """Register validation schemas"""
        
        if not HAS_MARSHMALLOW:
            return
        
        # User registration schema
        class UserRegistrationSchema(Schema):
            username = fields.Str(required=True, validate=lambda x: len(x) >= 3)
            email = fields.Email(required=True)
            password = fields.Str(required=True, validate=lambda x: len(x) >= 8)
            age = fields.Int(required=True, validate=lambda x: 18 <= x <= 120)
            
            @validates('username')
            def validate_username(self, value):
                if not re.match(r'^[a-zA-Z0-9_]+$', value):
                    raise ValidationError('Username contains invalid characters')
            
            @validates('password')
            def validate_password(self, value):
                if not re.search(r'[A-Z]', value):
                    raise ValidationError('Password must contain uppercase letter')
                if not re.search(r'[a-z]', value):
                    raise ValidationError('Password must contain lowercase letter')
                if not re.search(r'[0-9]', value):
                    raise ValidationError('Password must contain digit')
        
        # Database query schema
        class QuerySchema(Schema):
            table_name = fields.Str(required=True)
            columns = fields.List(fields.Str(), required=True)
            where_clause = fields.Str(allow_none=True)
            limit = fields.Int(validate=lambda x: 1 <= x <= 1000)
            
            @validates('table_name')
            def validate_table_name(self, value):
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', value):
                    raise ValidationError('Invalid table name')
        
        self.schema_validator.register_schema('user_registration', UserRegistrationSchema())
        self.schema_validator.register_schema('query', QuerySchema())
    
    def demonstrate_string_sanitization(self):
        """Demonstrate string sanitization"""
        
        print("String Sanitization Demo")
        print("=" * 50)
        
        test_strings = [
            "Normal string",
            "String with\x00null bytes",
            "String    with   extra   spaces",
            "String\nwith\r\nline\tbreaks",
            "String with \x01control\x02 characters",
            "A" * 1000,  # Very long string
        ]
        
        for i, test_string in enumerate(test_strings, 1):
            print(f"\n{i}. Testing: {repr(test_string[:50])}")
            
            result = self.sanitizer.sanitize_string(test_string, max_length=100)
            
            if result.is_valid:
                print(f"   ✅ Valid: {repr(result.sanitized_data)}")
            else:
                print(f"   ❌ Invalid: {', '.join(result.errors)}")
            
            if result.warnings:
                print(f"   ⚠️  Warnings: {', '.join(result.warnings)}")
    
    def demonstrate_html_sanitization(self):
        """Demonstrate HTML sanitization"""
        
        print("\n\nHTML Sanitization Demo")
        print("=" * 50)
        
        test_html = [
            "<p>Normal paragraph</p>",
            "<script>alert('XSS')</script>",
            "<b>Bold text</b>",
            "<img src='x' onerror='alert(1)'>",
            "<a href='javascript:alert(1)'>Link</a>",
            "<div onclick='alert(1)'>Click me</div>",
            "Plain text with <b>some</b> formatting",
        ]
        
        for i, html in enumerate(test_html, 1):
            print(f"\n{i}. Testing: {html}")
            
            result = self.sanitizer.sanitize_html(html)
            
            if result.is_valid:
                print(f"   ✅ Sanitized: {result.sanitized_data}")
            else:
                print(f"   ❌ Invalid: {', '.join(result.errors)}")
            
            if result.warnings:
                print(f"   ⚠️  Warnings: {', '.join(result.warnings)}")
    
    def demonstrate_sql_sanitization(self):
        """Demonstrate SQL identifier sanitization"""
        
        print("\n\nSQL Identifier Sanitization Demo")
        print("=" * 50)
        
        test_identifiers = [
            "users",
            "user_profiles",
            "SELECT",  # Reserved word
            "table-name",  # Invalid character
            "123invalid",  # Starts with number
            "valid_table_name",
            "a" * 70,  # Too long
        ]
        
        for i, identifier in enumerate(test_identifiers, 1):
            print(f"\n{i}. Testing: {identifier}")
            
            result = self.sanitizer.sanitize_sql_identifier(identifier)
            
            if result.is_valid:
                print(f"   ✅ Valid identifier: {result.sanitized_data}")
            else:
                print(f"   ❌ Invalid: {', '.join(result.errors)}")
    
    def demonstrate_url_validation(self):
        """Demonstrate URL validation"""
        
        print("\n\nURL Validation Demo")
        print("=" * 50)
        
        test_urls = [
            "https://example.com",
            "http://localhost:3000",
            "https://192.168.1.1",
            "ftp://example.com",  # Wrong protocol
            "https://example.com/path?param=value",
            "javascript:alert(1)",  # Dangerous
            "https://example.com/<script>",  # Suspicious
        ]
        
        for i, url in enumerate(test_urls, 1):
            print(f"\n{i}. Testing: {url}")
            
            result = self.sanitizer.sanitize_url(url)
            
            if result.is_valid:
                print(f"   ✅ Valid URL: {result.sanitized_data}")
            else:
                print(f"   ❌ Invalid: {', '.join(result.errors)}")
            
            if result.warnings:
                print(f"   ⚠️  Warnings: {', '.join(result.warnings)}")
    
    def demonstrate_json_validation(self):
        """Demonstrate JSON validation"""
        
        print("\n\nJSON Validation Demo")
        print("=" * 50)
        
        test_json = [
            '{"name": "John", "age": 30}',
            '{"deeply": {"nested": {"object": {"value": 1}}}}',
            '{"array": [1, 2, 3]}',
            '{"invalid": "json"',  # Invalid JSON
            '{"string": "with\x00null"}',  # String with null byte
            '{"very": {"deep": {"nesting": {"goes": {"on": {"forever": {"and": {"ever": {"value": 1}}}}}}}}}',
        ]
        
        for i, json_str in enumerate(test_json, 1):
            print(f"\n{i}. Testing: {json_str}")
            
            result = self.sanitizer.sanitize_json(json_str, max_depth=5)
            
            if result.is_valid:
                print(f"   ✅ Valid JSON: {json.dumps(result.sanitized_data, indent=2)}")
            else:
                print(f"   ❌ Invalid: {', '.join(result.errors)}")
    
    def demonstrate_schema_validation(self):
        """Demonstrate schema validation"""
        
        print("\n\nSchema Validation Demo")
        print("=" * 50)
        
        if not HAS_MARSHMALLOW:
            print("   ⚠️  Marshmallow not available - skipping schema validation")
            return
        
        # Test user registration
        print("\n1. User Registration Validation:")
        
        user_data = [
            {
                "username": "johndoe",
                "email": "john@example.com",
                "password": "SecurePass123",
                "age": 25
            },
            {
                "username": "a",  # Too short
                "email": "invalid-email",
                "password": "weak",
                "age": 15  # Too young
            },
            {
                "username": "user@invalid",  # Invalid characters
                "email": "user@example.com",
                "password": "NoNumbersHere",  # No digits
                "age": 30
            }
        ]
        
        for i, data in enumerate(user_data, 1):
            print(f"\n   Test {i}: {data}")
            
            result = self.schema_validator.validate('user_registration', data)
            
            if result.is_valid:
                print(f"   ✅ Valid user data")
            else:
                print(f"   ❌ Validation errors:")
                for error in result.errors:
                    print(f"      - {error}")
    
    @rate_limit(max_requests=3, window_seconds=5)
    def demonstrate_rate_limiting(self):
        """Demonstrate rate limiting"""
        
        print("\n\nRate Limiting Demo")
        print("=" * 50)
        
        print("\n1. Making requests (limit: 3 per 5 seconds):")
        
        for i in range(6):
            try:
                # This function is rate limited
                remaining = self.rate_limiter.get_remaining_requests('demo')
                print(f"   Request {i+1}: Success (remaining: {remaining})")
                
            except ValidationError as e:
                print(f"   Request {i+1}: {e}")
    
    def demonstrate_comprehensive_validation(self):
        """Demonstrate comprehensive validation pipeline"""
        
        print("\n\nComprehensive Validation Pipeline Demo")
        print("=" * 50)
        
        # Simulate processing user input
        user_input = {
            "username": "test_user",
            "bio": "<script>alert('xss')</script>Hello <b>world</b>!",
            "website": "https://example.com/profile",
            "search_query": "SELECT * FROM users WHERE id = 1",
            "profile_data": '{"interests": ["coding", "security"], "location": "SF"}'
        }
        
        print("\n1. Processing user input:")
        print(f"   Raw input: {user_input}")
        
        # Validate and sanitize each field
        processed_data = {}
        
        # Username
        result = self.sanitizer.sanitize_sql_identifier(user_input["username"])
        if result.is_valid:
            processed_data["username"] = result.sanitized_data
            print(f"   ✅ Username: {result.sanitized_data}")
        else:
            print(f"   ❌ Username invalid: {', '.join(result.errors)}")
        
        # Bio (HTML content)
        result = self.sanitizer.sanitize_html(user_input["bio"])
        if result.is_valid:
            processed_data["bio"] = result.sanitized_data
            print(f"   ✅ Bio: {result.sanitized_data}")
        else:
            print(f"   ❌ Bio invalid: {', '.join(result.errors)}")
        
        # Website URL
        result = self.sanitizer.sanitize_url(user_input["website"])
        if result.is_valid:
            processed_data["website"] = result.sanitized_data
            print(f"   ✅ Website: {result.sanitized_data}")
        else:
            print(f"   ❌ Website invalid: {', '.join(result.errors)}")
        
        # Search query (treat as string)
        result = self.sanitizer.sanitize_string(user_input["search_query"])
        if result.is_valid:
            processed_data["search_query"] = result.sanitized_data
            print(f"   ✅ Search query: {result.sanitized_data}")
        else:
            print(f"   ❌ Search query invalid: {', '.join(result.errors)}")
        
        # Profile data (JSON)
        result = self.sanitizer.sanitize_json(user_input["profile_data"])
        if result.is_valid:
            processed_data["profile_data"] = result.sanitized_data
            print(f"   ✅ Profile data: {result.sanitized_data}")
        else:
            print(f"   ❌ Profile data invalid: {', '.join(result.errors)}")
        
        print(f"\n2. Final processed data:")
        print(f"   {json.dumps(processed_data, indent=2)}")


def main():
    """Run input validation demonstrations"""
    
    print("SpacetimeDB Input Validation Demo")
    print("=" * 50)
    
    demo = InputValidationDemo()
    
    try:
        demo.demonstrate_string_sanitization()
        demo.demonstrate_html_sanitization()
        demo.demonstrate_sql_sanitization()
        demo.demonstrate_url_validation()
        demo.demonstrate_json_validation()
        demo.demonstrate_schema_validation()
        demo.demonstrate_rate_limiting()
        demo.demonstrate_comprehensive_validation()
        
        print("\n" + "=" * 50)
        print("✅ Input validation demo completed!")
        print("🔒 Always validate and sanitize user input")
        print("🚫 Never trust data from external sources")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()