"""
Migration Utilities for Unified Event System

This module provides utilities to help migrate from the old scattered
event systems to the new unified event system.
"""

import os
import ast
import re
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import argparse


@dataclass
class MigrationAnalysis:
    """Analysis results for migration."""
    files_analyzed: int = 0
    legacy_patterns_found: int = 0
    handlers_detected: int = 0
    event_types_found: Set[str] = field(default_factory=set)
    migration_suggestions: List[str] = field(default_factory=list)
    compatibility_issues: List[str] = field(default_factory=list)
    estimated_effort: str = "unknown"


class LegacyPatternDetector:
    """Detects legacy event system patterns in code."""
    
    def __init__(self):
        self.legacy_patterns = {
            'old_event_system': [
                r'from\s+spacetimedb_sdk\.event_system\s+import',
                r'import\s+spacetimedb_sdk\.event_system',
                r'EventEmitter\(\)',
                r'\.on\(["\'][\w_]+["\']',
                r'\.emit\(["\'][\w_]+["\']',
                r'\.off\(["\'][\w_]+["\']'
            ],
            'old_event_manager': [
                r'from\s+spacetimedb_sdk\.event_manager\s+import',
                r'import\s+spacetimedb_sdk\.event_manager',
                r'SDKEventManager\(\)',
                r'\.register_callback\(',
                r'\.queue_event\(',
                r'\.process_events\(\)'
            ],
            'websocket_events': [
                r'websocket\.on_open',
                r'websocket\.on_close',
                r'websocket\.on_message',
                r'websocket\.on_error',
                r'\.on_connect\(',
                r'\.on_disconnect\(',
                r'\.on_message\('
            ]
        }
        
        self.event_names = {
            'connection_events': [
                'connected', 'disconnected', 'connection_error', 'reconnecting',
                'timeout', 'heartbeat', 'open', 'close', 'error'
            ],
            'auth_events': [
                'authenticated', 'auth_failed', 'auth_expired', 'auth_refresh',
                'login', 'logout'
            ],
            'message_events': [
                'message_received', 'message_sent', 'message_error',
                'message_queued', 'message'
            ],
            'database_events': [
                'table_update', 'reducer_call', 'transaction_committed',
                'schema_updated', 'database_error'
            ],
            'system_events': [
                'error', 'warning', 'ready', 'shutdown', 'system_error'
            ]
        }
    
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze a single file for legacy patterns."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            analysis = {
                'file_path': file_path,
                'legacy_patterns': {},
                'event_types': set(),
                'handlers': [],
                'migration_complexity': 'low'
            }
            
            # Check for legacy patterns
            for category, patterns in self.legacy_patterns.items():
                matches = []
                for pattern in patterns:
                    found = re.findall(pattern, content, re.IGNORECASE)
                    if found:
                        matches.extend(found)
                
                if matches:
                    analysis['legacy_patterns'][category] = matches
            
            # Find event types
            for category, events in self.event_names.items():
                for event in events:
                    if re.search(rf'["\']({re.escape(event)})["\']', content):
                        analysis['event_types'].add(event)
            
            # Find handler patterns
            handler_patterns = [
                r'def\s+on_(\w+)\s*\(',
                r'def\s+handle_(\w+)\s*\(',
                r'lambda.*:\s*\w+',
                r'\.on\(["\'][\w_]+["\'],\s*(\w+)\)'
            ]
            
            for pattern in handler_patterns:
                matches = re.findall(pattern, content)
                analysis['handlers'].extend(matches)
            
            # Assess complexity
            total_patterns = sum(len(patterns) for patterns in analysis['legacy_patterns'].values())
            if total_patterns > 20:
                analysis['migration_complexity'] = 'high'
            elif total_patterns > 10:
                analysis['migration_complexity'] = 'medium'
            
            return analysis
            
        except Exception as e:
            return {
                'file_path': file_path,
                'error': str(e),
                'legacy_patterns': {},
                'event_types': set(),
                'handlers': [],
                'migration_complexity': 'unknown'
            }
    
    def analyze_directory(self, directory: str) -> MigrationAnalysis:
        """Analyze a directory for legacy patterns."""
        analysis = MigrationAnalysis()
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    file_analysis = self.analyze_file(file_path)
                    
                    analysis.files_analyzed += 1
                    
                    if file_analysis.get('legacy_patterns'):
                        analysis.legacy_patterns_found += 1
                        analysis.handlers_detected += len(file_analysis.get('handlers', []))
                        analysis.event_types_found.update(file_analysis.get('event_types', set()))
                        
                        # Add migration suggestions
                        self._generate_suggestions(file_analysis, analysis)
        
        # Estimate effort
        if analysis.legacy_patterns_found == 0:
            analysis.estimated_effort = "none"
        elif analysis.legacy_patterns_found < 5:
            analysis.estimated_effort = "low"
        elif analysis.legacy_patterns_found < 15:
            analysis.estimated_effort = "medium"
        else:
            analysis.estimated_effort = "high"
        
        return analysis
    
    def _generate_suggestions(self, file_analysis: Dict[str, Any], overall_analysis: MigrationAnalysis):
        """Generate migration suggestions based on analysis."""
        file_path = file_analysis['file_path']
        
        if 'old_event_system' in file_analysis['legacy_patterns']:
            overall_analysis.migration_suggestions.append(
                f"Replace EventEmitter with UnifiedEventManager in {file_path}"
            )
        
        if 'old_event_manager' in file_analysis['legacy_patterns']:
            overall_analysis.migration_suggestions.append(
                f"Replace SDKEventManager with UnifiedEventManager in {file_path}"
            )
        
        if 'websocket_events' in file_analysis['legacy_patterns']:
            overall_analysis.migration_suggestions.append(
                f"Use WebSocketEventIntegration for WebSocket events in {file_path}"
            )
        
        if file_analysis['migration_complexity'] == 'high':
            overall_analysis.compatibility_issues.append(
                f"High complexity migration required for {file_path}"
            )


class MigrationCodeGenerator:
    """Generates migration code for different scenarios."""
    
    def __init__(self):
        self.event_type_mappings = {
            'connected': 'EventType.CONNECTION_OPENED',
            'disconnected': 'EventType.CONNECTION_CLOSED',
            'connection_error': 'EventType.CONNECTION_ERROR',
            'reconnecting': 'EventType.CONNECTION_RECONNECTING',
            'timeout': 'EventType.CONNECTION_TIMEOUT',
            'heartbeat': 'EventType.CONNECTION_HEARTBEAT',
            'authenticated': 'EventType.AUTHENTICATION_SUCCESS',
            'auth_failed': 'EventType.AUTHENTICATION_FAILED',
            'auth_expired': 'EventType.AUTHENTICATION_EXPIRED',
            'message_received': 'EventType.MESSAGE_RECEIVED',
            'message_sent': 'EventType.MESSAGE_SENT',
            'message_error': 'EventType.MESSAGE_ERROR',
            'table_update': 'EventType.TABLE_UPDATE',
            'reducer_call': 'EventType.REDUCER_CALL',
            'transaction_committed': 'EventType.TRANSACTION_COMMITTED',
            'database_error': 'EventType.DATABASE_ERROR',
            'error': 'EventType.SYSTEM_ERROR',
            'warning': 'EventType.PERFORMANCE_WARNING',
            'ready': 'EventType.SYSTEM_READY',
            'shutdown': 'EventType.SYSTEM_SHUTDOWN'
        }
    
    def generate_import_replacements(self) -> str:
        """Generate import replacement code."""
        return '''
# OLD IMPORTS (to be replaced):
# from spacetimedb_sdk.event_system import EventEmitter
# from spacetimedb_sdk.event_manager import SDKEventManager

# NEW IMPORTS:
from spacetimedb_sdk.events import (
    UnifiedEventManager,
    EventType,
    EventContext,
    EventPriority
)

# For backward compatibility during migration:
from spacetimedb_sdk.events.legacy_compat import (
    LegacyEventEmitter,
    LegacySDKEventManager
)
'''
    
    def generate_event_emitter_migration(self) -> str:
        """Generate EventEmitter migration code."""
        return '''
# OLD CODE:
# emitter = EventEmitter()
# emitter.on('connected', lambda: print('Connected'))
# emitter.emit('connected')

# NEW CODE (direct migration):
event_manager = UnifiedEventManager()

def on_connected(context: EventContext):
    print('Connected')
    # Access connection info: context.get_metadata('connection_id')
    # Access event data: context.data

event_manager.add_handler(EventType.CONNECTION_OPENED, on_connected)

context = EventContext.create(
    event_type=EventType.CONNECTION_OPENED,
    source="client",
    connection_id="conn_123"
)
event_manager.emit(EventType.CONNECTION_OPENED, context)

# COMPATIBILITY LAYER (for gradual migration):
legacy_emitter = LegacyEventEmitter(event_manager)
legacy_emitter.on('connected', lambda: print('Connected'))  # Still works!
legacy_emitter.emit('connected')
'''
    
    def generate_event_manager_migration(self) -> str:
        """Generate SDKEventManager migration code."""
        return '''
# OLD CODE:
# manager = SDKEventManager()
# manager.register_callback('table_update', lambda event: print(event))
# manager.queue_event('table_update', {'table': 'users'})

# NEW CODE (direct migration):
event_manager = UnifiedEventManager()

def on_table_update(context: EventContext):
    print(f"Table updated: {context.data}")
    # Access table info: context.get_metadata('table_name')
    # Access user info: context.get_metadata('user_id')

event_manager.add_handler(EventType.TABLE_UPDATE, on_table_update)

context = EventContext.create(
    event_type=EventType.TABLE_UPDATE,
    source="database",
    data={'table': 'users'},
    table_name="users"
)
event_manager.emit(EventType.TABLE_UPDATE, context)

# COMPATIBILITY LAYER (for gradual migration):
legacy_manager = LegacySDKEventManager(event_manager)
legacy_manager.register_callback('table_update', lambda event: print(event))
legacy_manager.queue_event('table_update', {'table': 'users'})
'''
    
    def generate_websocket_integration(self) -> str:
        """Generate WebSocket integration code."""
        return '''
# OLD CODE:
# websocket.on_open = lambda: print('WebSocket opened')
# websocket.on_message = lambda msg: print(f'Message: {msg}')
# websocket.on_close = lambda: print('WebSocket closed')

# NEW CODE (with integration):
from spacetimedb_sdk.events.websocket_integration import create_websocket_integration

event_manager = UnifiedEventManager()
websocket_integration = create_websocket_integration(event_manager)

# Register handlers for WebSocket events
def on_websocket_opened(context: EventContext):
    print(f'WebSocket opened: {context.get_metadata("connection_id")}')

def on_websocket_message(context: EventContext):
    print(f'Message received: {context.data}')

def on_websocket_closed(context: EventContext):
    print(f'WebSocket closed: {context.get_metadata("connection_id")}')

event_manager.add_handler(EventType.CONNECTION_OPENED, on_websocket_opened)
event_manager.add_handler(EventType.MESSAGE_RECEIVED, on_websocket_message)
event_manager.add_handler(EventType.CONNECTION_CLOSED, on_websocket_closed)

# Register your WebSocket client
websocket_integration.register_websocket_client(
    websocket_client,
    "conn_123",
    "ws://localhost:8080"
)
'''
    
    def generate_advanced_features(self) -> str:
        """Generate advanced features code."""
        return '''
# ADVANCED FEATURES (not available in old system):

# 1. Event Filtering
from spacetimedb_sdk.events.event_filters import TypeFilter, SourceFilter, CompositeFilter

# Only handle WebSocket connection events
websocket_filter = SourceFilter(["websocket_client"])
event_manager.add_handler(
    EventType.CONNECTION_OPENED,
    on_websocket_opened,
    event_filter=websocket_filter
)

# 2. Priority-based handlers
event_manager.add_handler(
    EventType.SYSTEM_ERROR,
    critical_error_handler,
    EventPriority.CRITICAL
)

# 3. Async handlers
async def async_message_handler(context: EventContext):
    await process_message_async(context.data)

event_manager.add_handler(EventType.MESSAGE_RECEIVED, async_message_handler)

# 4. Context management
from spacetimedb_sdk.events.event_context import ContextBuilder

context = (ContextBuilder(EventType.CONNECTION_OPENED)
          .source("websocket_client")
          .data({"connection_id": "conn_123"})
          .metadata(user_id="user_456")
          .build())

# 5. Performance monitoring
metrics = event_manager.get_metrics()
if metrics:
    health = metrics.get_system_health()
    print(f"Events per second: {health['events_per_second']}")
'''
    
    def generate_complete_migration_example(self, event_types: Set[str]) -> str:
        """Generate complete migration example for specific event types."""
        mapped_types = []
        for event_type in event_types:
            if event_type in self.event_type_mappings:
                mapped_types.append(self.event_type_mappings[event_type])
        
        return f'''
# COMPLETE MIGRATION EXAMPLE
# Events found in your code: {', '.join(event_types)}

from spacetimedb_sdk.events import (
    UnifiedEventManager,
    EventType,
    EventContext,
    EventPriority
)

# Create unified event manager
event_manager = UnifiedEventManager()

# Migrate your handlers
{self._generate_handler_examples(event_types)}

# Advanced configuration
from spacetimedb_sdk.events.event_manager import EventManagerConfig

config = EventManagerConfig(
    enable_metrics=True,
    enable_batching=True,
    thread_pool_size=4,
    debug_mode=False
)
event_manager = UnifiedEventManager(config)

# Performance monitoring
metrics = event_manager.get_metrics()
if metrics:
    print(f"System health: {{metrics.get_system_health()}}")

# Cleanup
event_manager.shutdown()
'''
    
    def _generate_handler_examples(self, event_types: Set[str]) -> str:
        """Generate handler examples for specific event types."""
        examples = []
        
        for event_type in event_types:
            if event_type in self.event_type_mappings:
                unified_type = self.event_type_mappings[event_type]
                handler_name = f"on_{event_type}"
                
                example = f'''
def {handler_name}(context: EventContext):
    print(f"Handling {event_type}: {{context.data}}")
    # Access metadata: context.get_metadata('key')
    # Access source: context.source
    # Access timestamp: context.timestamp

event_manager.add_handler({unified_type}, {handler_name})
'''
                examples.append(example)
        
        return '\n'.join(examples)


class MigrationPlanner:
    """Creates migration plans based on analysis."""
    
    def __init__(self):
        self.detector = LegacyPatternDetector()
        self.generator = MigrationCodeGenerator()
    
    def create_migration_plan(self, directory: str) -> Dict[str, Any]:
        """Create a comprehensive migration plan."""
        analysis = self.detector.analyze_directory(directory)
        
        plan = {
            'analysis': analysis,
            'phases': self._create_migration_phases(analysis),
            'code_examples': self._create_code_examples(analysis),
            'timeline': self._estimate_timeline(analysis),
            'resources': self._list_resources(),
            'checklist': self._create_checklist(analysis)
        }
        
        return plan
    
    def _create_migration_phases(self, analysis: MigrationAnalysis) -> List[Dict[str, Any]]:
        """Create migration phases."""
        phases = []
        
        # Phase 1: Setup
        phases.append({
            'phase': 1,
            'name': 'Setup and Preparation',
            'description': 'Install unified event system and setup compatibility layers',
            'tasks': [
                'Install updated SpacetimeDB SDK',
                'Add unified event system imports',
                'Create compatibility layer instances',
                'Run initial tests'
            ],
            'estimated_hours': 4
        })
        
        # Phase 2: Compatibility Layer
        if analysis.legacy_patterns_found > 0:
            phases.append({
                'phase': 2,
                'name': 'Compatibility Layer Implementation',
                'description': 'Implement compatibility layers for existing code',
                'tasks': [
                    'Replace old imports with compatibility imports',
                    'Create LegacyEventEmitter instances',
                    'Create LegacySDKEventManager instances',
                    'Test existing functionality'
                ],
                'estimated_hours': analysis.legacy_patterns_found * 2
            })
        
        # Phase 3: Handler Migration
        if analysis.handlers_detected > 0:
            phases.append({
                'phase': 3,
                'name': 'Handler Migration',
                'description': 'Migrate event handlers to new system',
                'tasks': [
                    'Convert handler signatures to use EventContext',
                    'Update event type names to EventType enum',
                    'Add filters and priorities where needed',
                    'Test migrated handlers'
                ],
                'estimated_hours': analysis.handlers_detected * 1.5
            })
        
        # Phase 4: Advanced Features
        phases.append({
            'phase': 4,
            'name': 'Advanced Features Integration',
            'description': 'Integrate advanced features like filtering and async handlers',
            'tasks': [
                'Add event filters where appropriate',
                'Convert suitable handlers to async',
                'Implement WebSocket integration',
                'Add performance monitoring'
            ],
            'estimated_hours': 8
        })
        
        # Phase 5: Cleanup
        phases.append({
            'phase': 5,
            'name': 'Cleanup and Optimization',
            'description': 'Remove compatibility layers and optimize',
            'tasks': [
                'Remove compatibility layer usage',
                'Optimize event handler performance',
                'Add comprehensive testing',
                'Update documentation'
            ],
            'estimated_hours': 6
        })
        
        return phases
    
    def _create_code_examples(self, analysis: MigrationAnalysis) -> Dict[str, str]:
        """Create code examples for migration."""
        examples = {}
        
        examples['imports'] = self.generator.generate_import_replacements()
        
        if 'old_event_system' in str(analysis.migration_suggestions):
            examples['event_emitter'] = self.generator.generate_event_emitter_migration()
        
        if 'old_event_manager' in str(analysis.migration_suggestions):
            examples['event_manager'] = self.generator.generate_event_manager_migration()
        
        if 'websocket_events' in str(analysis.migration_suggestions):
            examples['websocket'] = self.generator.generate_websocket_integration()
        
        examples['advanced'] = self.generator.generate_advanced_features()
        
        if analysis.event_types_found:
            examples['complete'] = self.generator.generate_complete_migration_example(
                analysis.event_types_found
            )
        
        return examples
    
    def _estimate_timeline(self, analysis: MigrationAnalysis) -> Dict[str, Any]:
        """Estimate migration timeline."""
        base_hours = 8  # Minimum for setup and cleanup
        
        if analysis.estimated_effort == "low":
            total_hours = base_hours + 4
        elif analysis.estimated_effort == "medium":
            total_hours = base_hours + 16
        elif analysis.estimated_effort == "high":
            total_hours = base_hours + 32
        else:
            total_hours = base_hours
        
        return {
            'estimated_hours': total_hours,
            'estimated_days': total_hours / 8,
            'effort_level': analysis.estimated_effort,
            'complexity_factors': [
                f"{analysis.legacy_patterns_found} files with legacy patterns",
                f"{analysis.handlers_detected} handlers to migrate",
                f"{len(analysis.event_types_found)} event types to convert"
            ]
        }
    
    def _list_resources(self) -> List[str]:
        """List migration resources."""
        return [
            'SpacetimeDB Python SDK Documentation',
            'Event System Migration Guide',
            'API Reference for UnifiedEventManager',
            'WebSocket Integration Examples',
            'Performance Monitoring Guide',
            'Compatibility Layer Reference',
            'Migration Code Examples'
        ]
    
    def _create_checklist(self, analysis: MigrationAnalysis) -> List[Dict[str, Any]]:
        """Create migration checklist."""
        checklist = [
            {
                'category': 'Preparation',
                'items': [
                    'Backup existing code',
                    'Update SpacetimeDB SDK to latest version',
                    'Review migration guide',
                    'Set up test environment'
                ]
            },
            {
                'category': 'Analysis',
                'items': [
                    'Run migration analysis tool',
                    'Identify all legacy event patterns',
                    'Document existing event handlers',
                    'Plan migration phases'
                ]
            },
            {
                'category': 'Implementation',
                'items': [
                    'Install compatibility layers',
                    'Update imports',
                    'Migrate event handlers',
                    'Add new event types',
                    'Test functionality'
                ]
            },
            {
                'category': 'Testing',
                'items': [
                    'Test existing functionality',
                    'Test new unified system',
                    'Performance testing',
                    'Error handling testing'
                ]
            },
            {
                'category': 'Optimization',
                'items': [
                    'Remove compatibility layers',
                    'Optimize handler performance',
                    'Add monitoring',
                    'Update documentation'
                ]
            }
        ]
        
        return checklist


def main():
    """Main CLI for migration utilities."""
    parser = argparse.ArgumentParser(description='SpacetimeDB Event System Migration Tool')
    parser.add_argument('directory', help='Directory to analyze')
    parser.add_argument('--output', '-o', help='Output file for migration plan')
    parser.add_argument('--format', '-f', choices=['json', 'text'], default='text',
                       help='Output format')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Create migration planner
    planner = MigrationPlanner()
    
    print(f"Analyzing directory: {args.directory}")
    plan = planner.create_migration_plan(args.directory)
    
    if args.format == 'json':
        # Convert sets to lists for JSON serialization
        analysis = plan['analysis']
        analysis.event_types_found = list(analysis.event_types_found)
        
        output = {
            'analysis': {
                'files_analyzed': analysis.files_analyzed,
                'legacy_patterns_found': analysis.legacy_patterns_found,
                'handlers_detected': analysis.handlers_detected,
                'event_types_found': analysis.event_types_found,
                'migration_suggestions': analysis.migration_suggestions,
                'compatibility_issues': analysis.compatibility_issues,
                'estimated_effort': analysis.estimated_effort
            },
            'phases': plan['phases'],
            'timeline': plan['timeline'],
            'checklist': plan['checklist']
        }
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(output, f, indent=2)
        else:
            print(json.dumps(output, indent=2))
    
    else:
        # Text format
        output = generate_text_report(plan)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
        else:
            print(output)


def generate_text_report(plan: Dict[str, Any]) -> str:
    """Generate text format migration report."""
    analysis = plan['analysis']
    
    report = f"""
SpacetimeDB Event System Migration Analysis Report
=================================================

Analysis Summary:
- Files analyzed: {analysis.files_analyzed}
- Files with legacy patterns: {analysis.legacy_patterns_found}
- Event handlers detected: {analysis.handlers_detected}
- Event types found: {len(analysis.event_types_found)}
- Estimated effort: {analysis.estimated_effort}

Event Types Found:
{', '.join(sorted(analysis.event_types_found)) if analysis.event_types_found else 'None'}

Migration Suggestions:
"""
    
    for suggestion in analysis.migration_suggestions:
        report += f"- {suggestion}\n"
    
    if analysis.compatibility_issues:
        report += "\nCompatibility Issues:\n"
        for issue in analysis.compatibility_issues:
            report += f"- {issue}\n"
    
    report += f"\nMigration Timeline:\n"
    timeline = plan['timeline']
    report += f"- Estimated hours: {timeline['estimated_hours']}\n"
    report += f"- Estimated days: {timeline['estimated_days']:.1f}\n"
    report += f"- Effort level: {timeline['effort_level']}\n"
    
    report += "\nMigration Phases:\n"
    for phase in plan['phases']:
        report += f"\nPhase {phase['phase']}: {phase['name']}\n"
        report += f"Description: {phase['description']}\n"
        report += f"Estimated hours: {phase['estimated_hours']}\n"
        report += "Tasks:\n"
        for task in phase['tasks']:
            report += f"  - {task}\n"
    
    report += "\nMigration Checklist:\n"
    for category in plan['checklist']:
        report += f"\n{category['category']}:\n"
        for item in category['items']:
            report += f"  [ ] {item}\n"
    
    return report


if __name__ == "__main__":
    main()