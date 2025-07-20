#!/usr/bin/env python3
"""
Basic Authentication Example - SpacetimeDB Python SDK

This example demonstrates basic authentication patterns with the SpacetimeDB Python SDK,
including credential setup, authentication flow, and error handling.

Key Features Demonstrated:
- Basic credential authentication
- Secure credential storage
- Authentication error handling
- Connection management with authentication
- Best practices for credential handling
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import logging
from typing import Optional
from spacetimedb_sdk import SpacetimeDBAsyncClient
from spacetimedb_sdk.auth import AuthenticationHandler
from spacetimedb_sdk.auth.storage import SecureAuthStorage
from spacetimedb_sdk.exceptions import AuthenticationError, ConnectionError


# Configure logging for better debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BasicAuthExample:
    """
    Example class demonstrating basic authentication patterns.
    
    This class shows how to properly handle authentication in a production
    environment with proper error handling and secure credential management.
    """
    
    def __init__(self, server_url: str = "ws://localhost:3000"):
        self.server_url = server_url
        self.client: Optional[SpacetimeDBAsyncClient] = None
        self.auth_handler: Optional[AuthenticationHandler] = None
        
    async def setup_authentication(self, database_name: str, identity_name: str) -> bool:
        """
        Set up authentication with secure credential storage.
        
        Args:
            database_name: Name of the SpacetimeDB database
            identity_name: Name for the user identity
            
        Returns:
            bool: True if authentication setup was successful
        """
        try:
            # Initialize secure credential storage
            auth_storage = SecureAuthStorage()
            
            # Create authentication handler
            self.auth_handler = AuthenticationHandler(
                storage=auth_storage,
                auto_refresh=True,  # Automatically refresh tokens
                refresh_threshold=300  # Refresh 5 minutes before expiry
            )
            
            # Check if we have existing credentials
            existing_token = await auth_storage.get_token(database_name)
            if existing_token:
                logger.info("Found existing authentication token")
                return True
            
            # Generate new credentials if none exist
            logger.info(f"Generating new credentials for identity: {identity_name}")
            success = await self.auth_handler.create_identity(
                database_name=database_name,
                identity_name=identity_name
            )
            
            if success:
                logger.info("Authentication setup completed successfully")
                return True
            else:
                logger.error("Failed to create new identity")
                return False
                
        except Exception as e:
            logger.error(f"Authentication setup failed: {e}")
            return False
    
    async def connect_with_authentication(self, database_name: str) -> bool:
        """
        Connect to SpacetimeDB with authentication.
        
        Args:
            database_name: Name of the database to connect to
            
        Returns:
            bool: True if connection was successful
        """
        try:
            if not self.auth_handler:
                raise AuthenticationError("Authentication handler not initialized")
            
            # Create client with authentication
            self.client = SpacetimeDBAsyncClient(
                server_url=self.server_url,
                auth_handler=self.auth_handler
            )
            
            # Connect to the database
            logger.info(f"Connecting to database: {database_name}")
            await self.client.connect(database_name)
            
            # Verify connection and authentication
            if self.client.is_connected():
                logger.info("Successfully connected with authentication")
                return True
            else:
                logger.error("Connection failed")
                return False
                
        except AuthenticationError as e:
            logger.error(f"Authentication failed: {e}")
            return False
        except ConnectionError as e:
            logger.error(f"Connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            return False
    
    async def handle_authentication_errors(self) -> None:
        """
        Demonstrate proper authentication error handling patterns.
        """
        try:
            # Attempt operation that might fail due to authentication
            await self.client.call_reducer("some_reducer", {})
            
        except AuthenticationError as e:
            # Handle authentication-specific errors
            logger.warning(f"Authentication error: {e}")
            
            # Try to refresh credentials
            if self.auth_handler:
                logger.info("Attempting to refresh credentials")
                refreshed = await self.auth_handler.refresh_credentials()
                
                if refreshed:
                    logger.info("Credentials refreshed successfully")
                    # Retry the operation
                    try:
                        await self.client.call_reducer("some_reducer", {})
                        logger.info("Operation succeeded after credential refresh")
                    except Exception as retry_error:
                        logger.error(f"Operation failed even after refresh: {retry_error}")
                else:
                    logger.error("Failed to refresh credentials")
                    # Handle complete authentication failure
                    await self.handle_complete_auth_failure()
        
        except Exception as e:
            logger.error(f"Non-authentication error: {e}")
    
    async def handle_complete_auth_failure(self) -> None:
        """
        Handle complete authentication failure scenarios.
        """
        logger.warning("Handling complete authentication failure")
        
        # Disconnect current session
        if self.client and self.client.is_connected():
            await self.client.disconnect()
        
        # Clear stored credentials
        if self.auth_handler:
            await self.auth_handler.clear_credentials()
        
        # Reinitialize authentication (would typically prompt user for new credentials)
        logger.info("Authentication cleared. Re-authentication required.")
    
    async def cleanup(self) -> None:
        """
        Clean up resources and disconnect.
        """
        try:
            if self.client and self.client.is_connected():
                logger.info("Disconnecting from SpacetimeDB")
                await self.client.disconnect()
            
            if self.auth_handler:
                await self.auth_handler.cleanup()
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def main():
    """
    Main example function demonstrating basic authentication flow.
    """
    # Configuration
    database_name = "example_database"
    identity_name = "example_user"
    server_url = "ws://localhost:3000"
    
    example = BasicAuthExample(server_url)
    
    try:
        # Step 1: Setup authentication
        logger.info("=== Setting up authentication ===")
        auth_success = await example.setup_authentication(database_name, identity_name)
        
        if not auth_success:
            logger.error("Authentication setup failed")
            return
        
        # Step 2: Connect with authentication
        logger.info("=== Connecting with authentication ===")
        connect_success = await example.connect_with_authentication(database_name)
        
        if not connect_success:
            logger.error("Connection failed")
            return
        
        # Step 3: Demonstrate authentication error handling
        logger.info("=== Demonstrating error handling ===")
        await example.handle_authentication_errors()
        
        # Step 4: Keep connection alive for demonstration
        logger.info("=== Connection established successfully ===")
        logger.info("Connection will be maintained for 10 seconds...")
        await asyncio.sleep(10)
        
    except KeyboardInterrupt:
        logger.info("Example interrupted by user")
    except Exception as e:
        logger.error(f"Example failed with error: {e}")
    finally:
        # Clean up
        logger.info("=== Cleaning up ===")
        await example.cleanup()


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())


"""
Best Practices Demonstrated:

1. **Secure Credential Storage**:
   - Use SecureAuthStorage for encrypted credential storage
   - Never store credentials in plain text
   - Use proper encryption for sensitive data

2. **Error Handling**:
   - Specific handling for AuthenticationError vs other exceptions
   - Graceful degradation when authentication fails
   - Proper cleanup in error scenarios

3. **Authentication Flow**:
   - Check for existing credentials before creating new ones
   - Automatic token refresh with configurable thresholds
   - Proper connection lifecycle management

4. **Logging**:
   - Comprehensive logging for debugging
   - No sensitive information in logs
   - Structured logging with appropriate levels

5. **Resource Management**:
   - Proper cleanup of connections and resources
   - Exception-safe resource handling
   - Clear separation of concerns

Usage Notes:
- Replace server_url with your SpacetimeDB server URL
- Ensure your SpacetimeDB server is running and accessible
- This example uses async/await patterns for modern Python development
- Error handling demonstrates production-ready patterns
"""