"""
Advanced Features Example - Leveraging New SDK Capabilities

This example demonstrates advanced features available after migration.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
from typing import Dict, Any
from spacetimedb_sdk import (
    # Connection management
    ConnectionPool,
    SpacetimeDBConnectionBuilder,
    
    # Event system
    EventType,
    EventFilter,
    subscribe_to_events,
    get_event_manager,
    
    # Authentication
    store_credentials,
    get_credentials,
    
    # Subscriptions
    AdvancedSubscriptionBuilder,
    SubscriptionStrategy,
    
    # Performance
    OptimizationProfile,
    configure_performance,
    PerformanceMonitor,
    
    # Utilities
    get_logger
)


class AdvancedSpacetimeDBApp:
    """Example app showcasing advanced SDK features."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.pool = None
        self.monitor = PerformanceMonitor()
        self.connections: Dict[str, Any] = {}
        
    async def setup_connection_pool(self):
        """Set up connection pooling for multiple databases."""
        self.pool = ConnectionPool(
            min_size=5,
            max_size=20,
            max_idle_time=300.0,  # 5 minutes
            health_check_interval=30.0  # 30 seconds
        )
        
        # Pre-warm connections for frequently used databases
        for db in ['users_db', 'analytics_db', 'cache_db']:
            conn = await self.pool.acquire(f"ws://localhost:3000/database/{db}")
            self.connections[db] = conn
            
    def setup_advanced_event_handling(self):
        """Configure advanced event handling with filters and metrics."""
        
        # Filter events for specific tables only
        user_table_filter = EventFilter(
            event_types=[EventType.TABLE_UPDATE],
            data_filter=lambda d: d.get('table_name') == 'users'
        )
        
        message_table_filter = EventFilter(
            event_types=[EventType.TABLE_UPDATE],
            data_filter=lambda d: d.get('table_name') == 'messages'
        )
        
        # Subscribe with filters
        subscribe_to_events(
            self.handle_user_updates,
            filter=user_table_filter,
            priority=100  # High priority
        )
        
        subscribe_to_events(
            self.handle_message_updates,
            filter=message_table_filter,
            priority=50
        )
        
        # Performance monitoring events
        subscribe_to_events(
            self.track_performance,
            [EventType.PERFORMANCE_METRIC]
        )
        
        # Error aggregation
        subscribe_to_events(
            self.aggregate_errors,
            [EventType.ERROR_OCCURRED, EventType.CONNECTION_ERROR, EventType.SUBSCRIPTION_ERROR]
        )
        
    async def handle_user_updates(self, context):
        """Handle user table updates with business logic."""
        operation = context.data.get('operation')
        user = context.data.get('row')
        
        if operation == 'insert':
            # Send welcome message for new users
            await self.send_welcome_message(user)
        elif operation == 'update':
            # Check for important field changes
            old_user = context.data.get('old_row')
            if old_user and old_user.get('email') != user.get('email'):
                await self.send_email_verification(user)
                
    async def handle_message_updates(self, context):
        """Handle message updates with caching."""
        operation = context.data.get('operation')
        message = context.data.get('row')
        
        # Update local cache
        if operation in ['insert', 'update']:
            await self.update_message_cache(message)
        elif operation == 'delete':
            await self.remove_from_cache(message['id'])
            
    def track_performance(self, context):
        """Track performance metrics."""
        metric = context.data
        self.monitor.record_metric(
            name=metric['name'],
            value=metric['value'],
            tags=metric.get('tags', {})
        )
        
    def aggregate_errors(self, context):
        """Aggregate errors for monitoring."""
        error_type = context.event_type
        error_data = context.data
        
        # Send to error tracking service
        self.logger.error(
            f"Error occurred: {error_type}",
            extra={
                'error_code': error_data.get('code'),
                'error_message': error_data.get('message'),
                'error_context': error_data.get('context')
            }
        )
        
    async def setup_optimized_subscriptions(self):
        """Set up subscriptions with advanced features."""
        # Build complex subscription with all features
        subscription = AdvancedSubscriptionBuilder() \
            .select("SELECT * FROM users WHERE active = true") \
            .select("SELECT * FROM messages WHERE created_at > NOW() - INTERVAL '24 hours'") \
            .select("SELECT * FROM notifications WHERE read = false") \
            .with_strategy(SubscriptionStrategy.PROGRESSIVE) \
            .with_batch_size(100) \
            .with_error_handler(self.handle_subscription_error) \
            .with_progress_callback(self.track_subscription_progress) \
            .with_auto_reconnect(max_retries=5) \
            .with_compression(threshold=1024) \
            .build()
            
        # Subscribe through the appropriate connection
        users_conn = self.connections['users_db']
        await users_conn.subscribe(subscription)
        
    def handle_subscription_error(self, error):
        """Handle subscription errors with retry logic."""
        self.logger.warning(f"Subscription error: {error}, will retry...")
        
    def track_subscription_progress(self, progress):
        """Track subscription loading progress."""
        self.logger.info(f"Subscription progress: {progress.percentage}% ({progress.rows_loaded} rows)")
        
    async def configure_performance_optimization(self):
        """Configure SDK for optimal performance."""
        # Apply a preset optimization profile
        OptimizationProfile.apply('high_throughput')
        
        # Or configure manually
        configure_performance(
            # Connection settings
            connection_pool_size=20,
            connection_timeout=5.0,
            
            # Event processing
            event_queue_size=10000,
            event_batch_size=100,
            event_processing_threads=4,
            
            # Message handling
            enable_compression=True,
            compression_level=6,
            compression_threshold=1024,  # Compress messages > 1KB
            
            # Batching
            enable_batching=True,
            batch_size=50,
            batch_timeout_ms=10,
            
            # Memory management
            max_memory_usage_mb=500,
            enable_memory_monitoring=True,
            
            # Caching
            enable_query_cache=True,
            cache_size_mb=100,
            cache_ttl_seconds=300
        )
        
    async def demonstrate_secure_authentication(self):
        """Show secure authentication patterns."""
        # Store credentials securely for multiple environments
        environments = {
            'production': {
                'host': 'spacetimedb.example.com',
                'database': 'prod_db',
                'identity': 'prod-identity-12345',
                'token': 'prod-token-secure'
            },
            'staging': {
                'host': 'staging.spacetimedb.example.com',
                'database': 'staging_db',
                'identity': 'staging-identity-67890',
                'token': 'staging-token-secure'
            }
        }
        
        for env_name, config in environments.items():
            store_credentials(
                identity=config['identity'],
                token=config['token'],
                host=config['host'],
                database=config['database']
            )
            
        # Retrieve and use credentials
        prod_creds = get_credentials('spacetimedb.example.com', 'prod_db')
        if prod_creds and not prod_creds.is_expired():
            self.logger.info(f"Using production credentials (expires in {prod_creds.expires_in()} seconds)")
            
    async def get_performance_stats(self):
        """Get and display performance statistics."""
        # Event system metrics
        event_metrics = get_event_manager().get_metrics()
        self.logger.info(f"Event metrics: {event_metrics}")
        
        # Connection pool metrics
        if self.pool:
            pool_metrics = self.pool.get_metrics()
            self.logger.info(f"Pool metrics: {pool_metrics}")
            
        # Custom performance metrics
        app_metrics = self.monitor.get_summary()
        self.logger.info(f"Application metrics: {app_metrics}")
        
    async def send_welcome_message(self, user):
        """Send welcome message to new user."""
        self.logger.info(f"Sending welcome message to user {user['id']}")
        
    async def send_email_verification(self, user):
        """Send email verification."""
        self.logger.info(f"Sending email verification to {user['email']}")
        
    async def update_message_cache(self, message):
        """Update message cache."""
        self.logger.debug(f"Updating cache for message {message['id']}")
        
    async def remove_from_cache(self, message_id):
        """Remove message from cache."""
        self.logger.debug(f"Removing message {message_id} from cache")
        
    async def run(self):
        """Run the application with all advanced features."""
        # Configure performance first
        await self.configure_performance_optimization()
        
        # Set up secure authentication
        await self.demonstrate_secure_authentication()
        
        # Initialize connection pool
        await self.setup_connection_pool()
        
        # Set up event handling
        self.setup_advanced_event_handling()
        
        # Set up subscriptions
        await self.setup_optimized_subscriptions()
        
        # Monitor performance
        self.monitor.start()
        
        # Run for a while and collect stats
        await asyncio.sleep(30)
        
        # Display performance statistics
        await self.get_performance_stats()
        
        # Graceful shutdown
        if self.pool:
            await self.pool.close()


async def main():
    """Run the advanced example."""
    app = AdvancedSpacetimeDBApp()
    await app.run()


if __name__ == "__main__":
    # Enable debug logging to see all features in action
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())