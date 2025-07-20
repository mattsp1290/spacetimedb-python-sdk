#!/usr/bin/env python3
"""
JWT Token Management Example - SpacetimeDB Python SDK

This example demonstrates advanced JWT token management patterns including:
- JWT token lifecycle management
- Automatic token refresh
- Token validation and expiry handling
- Secure token storage and retrieval
- Token-based authentication patterns

Key Features Demonstrated:
- JWT token creation and validation
- Automatic refresh mechanisms
- Token expiry detection and handling
- Secure token storage patterns
- Error recovery for token-related issues
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import logging
import time
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from spacetimedb_sdk import SpacetimeDBAsyncClient
from spacetimedb_sdk.auth import AuthenticationHandler
from spacetimedb_sdk.auth.storage import SecureAuthStorage
from spacetimedb_sdk.auth.providers import JWTAuthProvider
from spacetimedb_sdk.exceptions import AuthenticationError, TokenExpiredError


# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JWTTokenManager:
    """
    Advanced JWT token management class demonstrating production-ready patterns.
    
    This class shows how to handle JWT tokens securely including validation,
    refresh, storage, and error recovery.
    """
    
    def __init__(self, server_url: str = "ws://localhost:3000"):
        self.server_url = server_url
        self.client: Optional[SpacetimeDBAsyncClient] = None
        self.auth_handler: Optional[AuthenticationHandler] = None
        self.jwt_provider: Optional[JWTAuthProvider] = None
        
        # Token management configuration
        self.refresh_threshold = 300  # Refresh 5 minutes before expiry
        self.max_refresh_attempts = 3
        self.token_cache: Dict[str, Any] = {}
        
    async def initialize_jwt_authentication(self, database_name: str, 
                                          identity_name: str,
                                          jwt_secret: Optional[str] = None) -> bool:
        """
        Initialize JWT-based authentication with proper token management.
        
        Args:
            database_name: Name of the SpacetimeDB database
            identity_name: User identity name
            jwt_secret: Optional JWT secret for token validation
            
        Returns:
            bool: True if initialization was successful
        """
        try:
            # Initialize secure storage
            auth_storage = SecureAuthStorage()
            
            # Create JWT provider with advanced configuration
            self.jwt_provider = JWTAuthProvider(
                secret=jwt_secret,
                algorithm="HS256",
                token_expiry_seconds=3600,  # 1 hour
                refresh_threshold_seconds=self.refresh_threshold,
                enable_automatic_refresh=True
            )
            
            # Create authentication handler with JWT provider
            self.auth_handler = AuthenticationHandler(
                storage=auth_storage,
                auth_provider=self.jwt_provider,
                auto_refresh=True,
                refresh_threshold=self.refresh_threshold
            )
            
            # Check for existing valid token
            existing_token = await self._get_valid_token(database_name)
            if existing_token:
                logger.info("Found valid existing JWT token")
                return True
            
            # Create new JWT token
            logger.info(f"Creating new JWT token for identity: {identity_name}")
            token_created = await self._create_jwt_token(database_name, identity_name)
            
            if token_created:
                logger.info("JWT authentication initialized successfully")
                return True
            else:
                logger.error("Failed to create JWT token")
                return False
                
        except Exception as e:
            logger.error(f"JWT authentication initialization failed: {e}")
            return False
    
    async def _create_jwt_token(self, database_name: str, identity_name: str) -> bool:
        """
        Create a new JWT token with proper claims and expiry.
        
        Args:
            database_name: Database name for token scope
            identity_name: User identity
            
        Returns:
            bool: True if token creation was successful
        """
        try:
            # Token payload with standard and custom claims
            current_time = datetime.utcnow()
            payload = {
                "sub": identity_name,  # Subject (user identity)
                "iat": int(current_time.timestamp()),  # Issued at
                "exp": int((current_time + timedelta(hours=1)).timestamp()),  # Expires at
                "nbf": int(current_time.timestamp()),  # Not before
                "iss": "spacetimedb-python-sdk",  # Issuer
                "aud": database_name,  # Audience (database)
                "database": database_name,  # Custom claim
                "identity": identity_name,  # Custom claim
                "permissions": ["read", "write"],  # Custom permissions
                "token_type": "access",  # Token type
                "refresh_count": 0  # Track refresh count
            }
            
            # Create JWT token using provider
            token = await self.jwt_provider.create_token(payload)
            
            if token:
                # Store token securely
                await self.auth_handler.storage.store_token(database_name, token)
                
                # Cache token information for quick access
                self.token_cache[database_name] = {
                    "token": token,
                    "payload": payload,
                    "created_at": current_time,
                    "expires_at": datetime.fromtimestamp(payload["exp"])
                }
                
                logger.info("JWT token created and stored successfully")
                return True
            else:
                logger.error("Failed to create JWT token")
                return False
                
        except Exception as e:
            logger.error(f"JWT token creation failed: {e}")
            return False
    
    async def _get_valid_token(self, database_name: str) -> Optional[str]:
        """
        Get a valid token, refreshing if necessary.
        
        Args:
            database_name: Database name
            
        Returns:
            Optional[str]: Valid token or None if unavailable
        """
        try:
            # Check cache first
            if database_name in self.token_cache:
                cached_info = self.token_cache[database_name]
                if await self._is_token_valid(cached_info["token"]):
                    return cached_info["token"]
                else:
                    # Remove invalid token from cache
                    del self.token_cache[database_name]
            
            # Try to get token from storage
            stored_token = await self.auth_handler.storage.get_token(database_name)
            if stored_token and await self._is_token_valid(stored_token):
                return stored_token
            
            # Token is invalid or expired, try to refresh
            refreshed_token = await self._refresh_token(database_name)
            return refreshed_token
            
        except Exception as e:
            logger.error(f"Error getting valid token: {e}")
            return None
    
    async def _is_token_valid(self, token: str) -> bool:
        """
        Validate JWT token including expiry and signature.
        
        Args:
            token: JWT token to validate
            
        Returns:
            bool: True if token is valid
        """
        try:
            # Decode and validate token
            payload = await self.jwt_provider.validate_token(token)
            
            if not payload:
                return False
            
            # Check expiry with refresh threshold
            current_time = datetime.utcnow()
            expires_at = datetime.fromtimestamp(payload.get("exp", 0))
            
            # Consider token invalid if it expires within refresh threshold
            if expires_at <= current_time + timedelta(seconds=self.refresh_threshold):
                logger.info("Token will expire soon, marking as invalid for refresh")
                return False
            
            return True
            
        except TokenExpiredError:
            logger.info("Token has expired")
            return False
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False
    
    async def _refresh_token(self, database_name: str) -> Optional[str]:
        """
        Refresh an expired or expiring JWT token.
        
        Args:
            database_name: Database name
            
        Returns:
            Optional[str]: New token or None if refresh failed
        """
        try:
            # Get current token info
            current_token = await self.auth_handler.storage.get_token(database_name)
            if not current_token:
                logger.warning("No token available for refresh")
                return None
            
            # Decode current token to get payload (even if expired)
            try:
                payload = jwt.decode(current_token, options={"verify_signature": False})
            except Exception as e:
                logger.error(f"Failed to decode token for refresh: {e}")
                return None
            
            # Create new token with updated expiry and refresh count
            current_time = datetime.utcnow()
            new_payload = payload.copy()
            new_payload.update({
                "iat": int(current_time.timestamp()),
                "exp": int((current_time + timedelta(hours=1)).timestamp()),
                "nbf": int(current_time.timestamp()),
                "refresh_count": payload.get("refresh_count", 0) + 1
            })
            
            # Create new token
            new_token = await self.jwt_provider.create_token(new_payload)
            
            if new_token:
                # Store new token
                await self.auth_handler.storage.store_token(database_name, new_token)
                
                # Update cache
                self.token_cache[database_name] = {
                    "token": new_token,
                    "payload": new_payload,
                    "created_at": current_time,
                    "expires_at": datetime.fromtimestamp(new_payload["exp"])
                }
                
                logger.info(f"Token refreshed successfully (refresh count: {new_payload['refresh_count']})")
                return new_token
            else:
                logger.error("Failed to create refreshed token")
                return None
                
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return None
    
    async def connect_with_jwt(self, database_name: str) -> bool:
        """
        Connect to SpacetimeDB using JWT authentication.
        
        Args:
            database_name: Database to connect to
            
        Returns:
            bool: True if connection was successful
        """
        try:
            # Ensure we have a valid token
            valid_token = await self._get_valid_token(database_name)
            if not valid_token:
                logger.error("No valid JWT token available for connection")
                return False
            
            # Create client with JWT authentication
            self.client = SpacetimeDBAsyncClient(
                server_url=self.server_url,
                auth_handler=self.auth_handler
            )
            
            # Connect to database
            logger.info(f"Connecting to database with JWT: {database_name}")
            await self.client.connect(database_name)
            
            if self.client.is_connected():
                logger.info("Successfully connected with JWT authentication")
                
                # Start automatic token refresh monitoring
                asyncio.create_task(self._monitor_token_expiry(database_name))
                
                return True
            else:
                logger.error("JWT connection failed")
                return False
                
        except Exception as e:
            logger.error(f"JWT connection error: {e}")
            return False
    
    async def _monitor_token_expiry(self, database_name: str) -> None:
        """
        Monitor token expiry and refresh automatically.
        
        Args:
            database_name: Database name to monitor
        """
        try:
            while self.client and self.client.is_connected():
                # Check if token needs refresh
                if database_name in self.token_cache:
                    token_info = self.token_cache[database_name]
                    expires_at = token_info["expires_at"]
                    current_time = datetime.utcnow()
                    
                    # Refresh if within threshold
                    time_until_expiry = (expires_at - current_time).total_seconds()
                    if time_until_expiry <= self.refresh_threshold:
                        logger.info("Token expiry detected, refreshing...")
                        refreshed_token = await self._refresh_token(database_name)
                        
                        if refreshed_token:
                            logger.info("Token refreshed automatically")
                        else:
                            logger.error("Automatic token refresh failed")
                            break
                
                # Check every minute
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"Token monitoring error: {e}")
    
    async def get_token_info(self, database_name: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive token information for debugging.
        
        Args:
            database_name: Database name
            
        Returns:
            Optional[Dict]: Token information or None
        """
        try:
            token = await self._get_valid_token(database_name)
            if not token:
                return None
            
            # Decode token for information
            payload = jwt.decode(token, options={"verify_signature": False})
            
            return {
                "token_length": len(token),
                "issued_at": datetime.fromtimestamp(payload.get("iat", 0)),
                "expires_at": datetime.fromtimestamp(payload.get("exp", 0)),
                "subject": payload.get("sub"),
                "database": payload.get("database"),
                "permissions": payload.get("permissions", []),
                "refresh_count": payload.get("refresh_count", 0),
                "time_until_expiry": datetime.fromtimestamp(payload.get("exp", 0)) - datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting token info: {e}")
            return None
    
    async def cleanup(self) -> None:
        """
        Clean up resources and clear token cache.
        """
        try:
            # Disconnect client
            if self.client and self.client.is_connected():
                await self.client.disconnect()
            
            # Clear token cache
            self.token_cache.clear()
            
            # Cleanup authentication handler
            if self.auth_handler:
                await self.auth_handler.cleanup()
                
            logger.info("JWT token manager cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


async def main():
    """
    Main example demonstrating JWT token management.
    """
    database_name = "jwt_example_db"
    identity_name = "jwt_user"
    server_url = "ws://localhost:3000"
    jwt_secret = "your-secret-key-here"  # Use proper secret management in production
    
    token_manager = JWTTokenManager(server_url)
    
    try:
        # Initialize JWT authentication
        logger.info("=== Initializing JWT Authentication ===")
        init_success = await token_manager.initialize_jwt_authentication(
            database_name, identity_name, jwt_secret
        )
        
        if not init_success:
            logger.error("JWT initialization failed")
            return
        
        # Connect with JWT
        logger.info("=== Connecting with JWT ===")
        connect_success = await token_manager.connect_with_jwt(database_name)
        
        if not connect_success:
            logger.error("JWT connection failed")
            return
        
        # Display token information
        logger.info("=== Token Information ===")
        token_info = await token_manager.get_token_info(database_name)
        if token_info:
            for key, value in token_info.items():
                logger.info(f"{key}: {value}")
        
        # Keep connection alive and demonstrate token refresh
        logger.info("=== Maintaining Connection (30 seconds) ===")
        logger.info("Token will be automatically refreshed if needed...")
        await asyncio.sleep(30)
        
    except KeyboardInterrupt:
        logger.info("Example interrupted by user")
    except Exception as e:
        logger.error(f"Example failed: {e}")
    finally:
        logger.info("=== Cleaning up ===")
        await token_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())


"""
Advanced JWT Token Management Best Practices:

1. **Token Lifecycle Management**:
   - Automatic token creation with proper claims
   - Proactive token refresh before expiry
   - Secure token storage with encryption
   - Proper cleanup and cache management

2. **Security Best Practices**:
   - Use strong secrets for token signing
   - Include standard JWT claims (sub, iat, exp, etc.)
   - Validate tokens including signature and expiry
   - Never log sensitive token data

3. **Error Handling**:
   - Graceful handling of expired tokens
   - Automatic refresh with fallback strategies
   - Proper error propagation and logging
   - Recovery from authentication failures

4. **Performance Optimization**:
   - Token caching for quick access
   - Minimal token validation overhead
   - Efficient refresh strategies
   - Background monitoring tasks

5. **Monitoring and Debugging**:
   - Comprehensive token information retrieval
   - Refresh count tracking
   - Expiry monitoring and alerts
   - Structured logging for troubleshooting

Production Considerations:
- Use proper secret management systems (AWS Secrets Manager, etc.)
- Implement token rotation policies
- Monitor token usage patterns
- Set appropriate token expiry times based on security requirements
- Consider refresh token patterns for long-lived applications
"""