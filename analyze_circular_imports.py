#!/usr/bin/env python3
"""
Analyze circular dependencies in SpacetimeDB Python SDK

This script:
1. Maps all imports in the SDK
2. Detects circular dependencies
3. Categorizes imports as type-only vs runtime
4. Generates a comprehensive report
"""

import ast
import os
import sys
from typing import Dict, Set, List, Tuple, Optional
from pathlib import Path
import json
from collections import defaultdict, deque
from datetime import datetime


class ImportAnalyzer(ast.NodeVisitor):
    """AST visitor to extract import information from Python files."""
    
    def __init__(self, module_path: str):
        self.module_path = module_path
        self.imports: List[Dict[str, any]] = []
        self.in_type_checking = False
        self.in_function = False
        self.function_stack = []
        
    def visit_If(self, node):
        """Track TYPE_CHECKING blocks."""
        # Check if this is a TYPE_CHECKING block
        if (isinstance(node.test, ast.Attribute) and 
            isinstance(node.test.value, ast.Name) and
            node.test.value.id == 'typing' and
            node.test.attr == 'TYPE_CHECKING'):
            self.in_type_checking = True
            self.generic_visit(node)
            self.in_type_checking = False
        elif (isinstance(node.test, ast.Name) and
              node.test.id == 'TYPE_CHECKING'):
            self.in_type_checking = True
            self.generic_visit(node)
            self.in_type_checking = False
        else:
            self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        """Track function definitions for lazy imports."""
        self.function_stack.append(node.name)
        self.in_function = True
        self.generic_visit(node)
        self.function_stack.pop()
        self.in_function = len(self.function_stack) > 0
    
    def visit_AsyncFunctionDef(self, node):
        """Track async function definitions for lazy imports."""
        self.visit_FunctionDef(node)
    
    def visit_Import(self, node):
        """Record import statements."""
        for alias in node.names:
            self.imports.append({
                'type': 'import',
                'module': alias.name,
                'alias': alias.asname,
                'is_type_only': self.in_type_checking,
                'is_lazy': self.in_function,
                'in_function': self.function_stack[-1] if self.function_stack else None,
                'line': node.lineno
            })
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """Record from ... import statements."""
        # Handle relative imports
        if node.level > 0:
            # Calculate the actual module based on current module and level
            parts = self.module_path.split('.')
            if node.level <= len(parts):
                base_parts = parts[:-node.level]
                if node.module:
                    module = '.'.join(base_parts) + '.' + node.module
                else:
                    module = '.'.join(base_parts)
            else:
                module = node.module or ''
        else:
            module = node.module or ''
        
        for alias in node.names:
            self.imports.append({
                'type': 'from_import',
                'module': module,
                'name': alias.name,
                'alias': alias.asname,
                'is_type_only': self.in_type_checking,
                'is_lazy': self.in_function,
                'in_function': self.function_stack[-1] if self.function_stack else None,
                'level': node.level,
                'line': node.lineno
            })
        self.generic_visit(node)


def analyze_file(file_path: Path, base_path: Path) -> Dict[str, any]:
    """Analyze a single Python file for imports."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        
        # Calculate module path
        relative_path = file_path.relative_to(base_path)
        module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
        if module_parts[-1] == '__init__':
            module_parts = module_parts[:-1]
        module_path = '.'.join(module_parts)
        
        analyzer = ImportAnalyzer(module_path)
        analyzer.visit(tree)
        
        return {
            'file': str(file_path.relative_to(base_path)),
            'module': module_path,
            'imports': analyzer.imports
        }
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return None


def build_dependency_graph(analyses: List[Dict]) -> Dict[str, Set[str]]:
    """Build a dependency graph from import analyses."""
    graph = defaultdict(set)
    
    for analysis in analyses:
        if not analysis:
            continue
            
        module = analysis['module']
        
        for imp in analysis['imports']:
            # Skip type-only imports for circular dependency detection
            if imp['is_type_only']:
                continue
                
            imported_module = imp['module']
            
            # Handle relative imports to spacetimedb_sdk modules
            if imported_module.startswith('spacetimedb_sdk'):
                # For from imports, we need the base module
                if imp['type'] == 'from_import':
                    # If importing from a module, use that module
                    graph[module].add(imported_module)
                else:
                    # For direct imports
                    graph[module].add(imported_module)
    
    return dict(graph)


def find_circular_dependencies(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Find all circular dependencies using DFS."""
    def dfs(node: str, path: List[str], visited: Set[str], rec_stack: Set[str], cycles: Set[Tuple[str]]):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path, visited, rec_stack, cycles)
            elif neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                # Normalize the cycle (start with smallest node)
                min_idx = cycle.index(min(cycle))
                normalized = tuple(cycle[min_idx:] + cycle[:min_idx])
                cycles.add(normalized)
        
        path.pop()
        rec_stack.remove(node)
    
    visited = set()
    cycles = set()
    
    for node in graph:
        if node not in visited:
            dfs(node, [], visited, set(), cycles)
    
    return [list(cycle) for cycle in cycles]


def categorize_imports(analyses: List[Dict]) -> Dict[str, Dict]:
    """Categorize imports by type (runtime vs type-only vs lazy)."""
    categories = {
        'runtime': [],
        'type_only': [],
        'lazy': []
    }
    
    import_details = {}
    
    for analysis in analyses:
        if not analysis:
            continue
            
        module = analysis['module']
        import_details[module] = {
            'runtime': [],
            'type_only': [],
            'lazy': []
        }
        
        for imp in analysis['imports']:
            import_info = {
                'from_module': module,
                'imported': imp['module'],
                'name': imp.get('name', ''),
                'line': imp['line']
            }
            
            if imp['is_type_only']:
                categories['type_only'].append(import_info)
                import_details[module]['type_only'].append(import_info)
            elif imp['is_lazy']:
                categories['lazy'].append(import_info)
                import_details[module]['lazy'].append(import_info)
            else:
                categories['runtime'].append(import_info)
                import_details[module]['runtime'].append(import_info)
    
    return categories, import_details


def generate_report(base_path: Path, analyses: List[Dict], graph: Dict[str, Set[str]], 
                   circular_deps: List[List[str]], categories: Dict, import_details: Dict):
    """Generate a comprehensive report of the analysis."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'base_path': str(base_path),
        'summary': {
            'total_modules': len(analyses),
            'total_imports': sum(len(a['imports']) for a in analyses if a),
            'circular_dependencies_found': len(circular_deps),
            'import_categories': {
                'runtime': len(categories['runtime']),
                'type_only': len(categories['type_only']),
                'lazy': len(categories['lazy'])
            }
        },
        'circular_dependencies': circular_deps,
        'dependency_graph': {k: list(v) for k, v in graph.items()},
        'import_details': import_details,
        'problematic_imports': []
    }
    
    # Identify problematic imports (those involved in circular dependencies)
    involved_modules = set()
    for cycle in circular_deps:
        involved_modules.update(cycle)
    
    for module in involved_modules:
        if module in import_details:
            runtime_imports = import_details[module]['runtime']
            for imp in runtime_imports:
                if imp['imported'] in involved_modules:
                    report['problematic_imports'].append({
                        'module': module,
                        'imports': imp['imported'],
                        'line': imp['line'],
                        'suggestion': 'Consider moving to TYPE_CHECKING or making it lazy'
                    })
    
    return report


def main():
    """Main analysis function."""
    # Get the SDK source directory
    sdk_path = Path('src/spacetimedb_sdk')
    
    if not sdk_path.exists():
        print(f"Error: SDK source directory not found at {sdk_path}")
        sys.exit(1)
    
    print("Analyzing SpacetimeDB Python SDK for circular dependencies...")
    print("=" * 60)
    
    # Find all Python files
    python_files = list(sdk_path.rglob('*.py'))
    print(f"Found {len(python_files)} Python files to analyze")
    
    # Analyze each file
    analyses = []
    for file_path in python_files:
        analysis = analyze_file(file_path, sdk_path)
        if analysis:
            analyses.append(analysis)
    
    # Build dependency graph
    graph = build_dependency_graph(analyses)
    
    # Find circular dependencies
    circular_deps = find_circular_dependencies(graph)
    
    # Categorize imports
    categories, import_details = categorize_imports(analyses)
    
    # Generate report
    report = generate_report(sdk_path, analyses, graph, circular_deps, categories, import_details)
    
    # Save detailed report as JSON
    with open('circular_import_analysis.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print(f"\nAnalysis Complete!")
    print(f"Total modules analyzed: {report['summary']['total_modules']}")
    print(f"Total imports found: {report['summary']['total_imports']}")
    print(f"  - Runtime imports: {report['summary']['import_categories']['runtime']}")
    print(f"  - Type-only imports: {report['summary']['import_categories']['type_only']}")
    print(f"  - Lazy imports: {report['summary']['import_categories']['lazy']}")
    
    print(f"\nCircular dependencies found: {len(circular_deps)}")
    for i, cycle in enumerate(circular_deps):
        print(f"  {i+1}. {' → '.join(cycle)}")
    
    if report['problematic_imports']:
        print(f"\nProblematic imports that need attention:")
        for prob in report['problematic_imports']:
            print(f"  - {prob['module']} imports {prob['imports']} at line {prob['line']}")
            print(f"    Suggestion: {prob['suggestion']}")
    
    print(f"\nDetailed report saved to: circular_import_analysis.json")
    
    # Test if the module can be imported
    print("\nTesting module import...")
    try:
        sys.path.insert(0, 'src')
        import spacetimedb_sdk
        print("❌ ERROR: Module imports successfully but circular dependency exists!")
        print("   This might cause issues in certain environments or with certain import orders.")
    except ImportError as e:
        print(f"✅ Import error detected (as expected): {e}")
    
    return report


if __name__ == '__main__':
    main()
