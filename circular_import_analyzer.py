#!/usr/bin/env python3
"""
Comprehensive circular import analysis tool for SpacetimeDB Python SDK.

This script analyzes the entire codebase to identify circular import dependencies
and generates a detailed report with dependency graphs.
"""

import os
import re
import ast
import json
from typing import Dict, List, Set, Tuple, Optional, Any
from pathlib import Path
from collections import defaultdict, deque


class ImportAnalyzer:
    """Analyzes Python imports to detect circular dependencies."""
    
    def __init__(self, src_dir: str):
        self.src_dir = Path(src_dir)
        self.modules: Dict[str, Set[str]] = {}  # module -> set of imports
        self.file_to_module: Dict[str, str] = {}  # file path -> module name
        self.module_to_file: Dict[str, str] = {}  # module name -> file path
        self.circular_chains: List[List[str]] = []
        
    def get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name."""
        relative_path = file_path.relative_to(self.src_dir)
        if relative_path.name == "__init__.py":
            # Package module
            return str(relative_path.parent).replace(os.sep, '.')
        else:
            # Regular module
            return str(relative_path.with_suffix('')).replace(os.sep, '.')
    
    def extract_imports_from_file(self, file_path: Path) -> Set[str]:
        """Extract all imports from a Python file."""
        imports = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            return imports
        
        # Parse with AST for accuracy
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
                        # Also add specific imports
                        for alias in node.names:
                            imports.add(f"{node.module}.{alias.name}")
        except SyntaxError:
            pass
        
        # Regex fallback for dynamic imports
        import_patterns = [
            r'from\s+([.\w]+)\s+import',
            r'import\s+([.\w]+)',
        ]
        
        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                imports.add(match)
        
        return imports
    
    def normalize_import(self, import_name: str, current_module: str) -> Optional[str]:
        """Normalize import name to absolute module name."""
        if import_name.startswith('.'):
            # Relative import
            parts = current_module.split('.')
            level = len(import_name) - len(import_name.lstrip('.'))
            if level > len(parts):
                return None
            
            base_parts = parts[:-level] if level > 0 else parts
            if import_name[level:]:
                return '.'.join(base_parts + [import_name[level:]])
            else:
                return '.'.join(base_parts)
        else:
            # Absolute import
            return import_name
    
    def analyze_directory(self):
        """Analyze all Python files in the directory."""
        python_files = list(self.src_dir.rglob("*.py"))
        
        # First pass: collect all modules and their imports
        for file_path in python_files:
            module_name = self.get_module_name(file_path)
            self.file_to_module[str(file_path)] = module_name
            self.module_to_file[module_name] = str(file_path)
            
            raw_imports = self.extract_imports_from_file(file_path)
            normalized_imports = set()
            
            for import_name in raw_imports:
                normalized = self.normalize_import(import_name, module_name)
                if normalized and normalized.startswith('spacetimedb_sdk'):
                    normalized_imports.add(normalized)
            
            self.modules[module_name] = normalized_imports
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """Find all circular dependency chains using DFS."""
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(module: str) -> bool:
            if module in rec_stack:
                # Found a cycle
                cycle_start = path.index(module)
                cycle = path[cycle_start:] + [module]
                self.circular_chains.append(cycle)
                return True
            
            if module in visited:
                return False
            
            visited.add(module)
            rec_stack.add(module)
            path.append(module)
            
            # Check imports
            for imported_module in self.modules.get(module, set()):
                # Only consider internal imports
                if imported_module in self.modules:
                    if dfs(imported_module):
                        return True
            
            rec_stack.remove(module)
            path.pop()
            return False
        
        # Try starting DFS from each module
        for module in self.modules:
            if module not in visited:
                dfs(module)
        
        return self.circular_chains
    
    def generate_dependency_graph(self) -> Dict[str, List[str]]:
        """Generate a dependency graph for visualization."""
        graph = {}
        for module, imports in self.modules.items():
            internal_imports = [imp for imp in imports if imp in self.modules]
            graph[module] = internal_imports
        return graph
    
    def analyze_specific_chain(self, modules: List[str]) -> Dict[str, Any]:
        """Analyze a specific import chain for detailed information."""
        analysis = {
            "chain": modules,
            "details": []
        }
        
        for i in range(len(modules) - 1):
            current = modules[i]
            next_module = modules[i + 1]
            
            detail = {
                "from": current,
                "to": next_module,
                "file": self.module_to_file.get(current),
                "imports": []
            }
            
            # Find specific imports
            if current in self.modules:
                for imp in self.modules[current]:
                    if imp == next_module or imp.startswith(next_module + '.'):
                        detail["imports"].append(imp)
            
            analysis["details"].append(detail)
        
        return analysis
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive analysis report."""
        self.analyze_directory()
        circular_deps = self.find_circular_dependencies()
        
        report = {
            "summary": {
                "total_modules": len(self.modules),
                "total_files": len(self.file_to_module),
                "circular_dependencies_found": len(circular_deps),
                "modules_affected": len(set(sum(circular_deps, [])))
            },
            "circular_dependencies": [],
            "dependency_graph": self.generate_dependency_graph(),
            "module_details": {}
        }
        
        # Analyze each circular dependency
        for chain in circular_deps:
            analysis = self.analyze_specific_chain(chain)
            report["circular_dependencies"].append(analysis)
        
        # Add module details
        for module, imports in self.modules.items():
            report["module_details"][module] = {
                "file": self.module_to_file.get(module),
                "imports": list(imports),
                "internal_imports": [imp for imp in imports if imp in self.modules]
            }
        
        return report


def main():
    """Main execution function."""
    src_dir = "/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk"
    
    print("🔍 Analyzing circular imports in SpacetimeDB Python SDK...")
    
    analyzer = ImportAnalyzer(src_dir)
    report = analyzer.generate_report()
    
    # Save detailed report
    with open("circular_import_analysis_detailed.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print(f"\n📊 Analysis Summary:")
    print(f"   Total modules analyzed: {report['summary']['total_modules']}")
    print(f"   Total files analyzed: {report['summary']['total_files']}")
    print(f"   Circular dependencies found: {report['summary']['circular_dependencies_found']}")
    print(f"   Modules affected: {report['summary']['modules_affected']}")
    
    if report["circular_dependencies"]:
        print(f"\n🔄 Circular Dependencies:")
        for i, dep in enumerate(report["circular_dependencies"], 1):
            print(f"   {i}. {' → '.join(dep['chain'])}")
    else:
        print(f"\n✅ No circular dependencies found!")
    
    print(f"\n📄 Detailed report saved to: circular_import_analysis_detailed.json")


if __name__ == "__main__":
    main()