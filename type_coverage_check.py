#!/usr/bin/env python3
"""
Type Coverage Checker for SpacetimeDB Python SDK

This script analyzes Python source files to calculate type annotation coverage.
It identifies functions and methods that are missing type annotations.
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, NamedTuple


class TypeAnalysis(NamedTuple):
    file_path: str
    total_functions: int
    typed_functions: int
    missing_annotations: List[str]


class TypeCoverageAnalyzer(ast.NodeVisitor):
    """AST visitor to analyze type annotations in Python code."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.total_functions = 0
        self.typed_functions = 0
        self.missing_annotations: List[str] = []
        self.current_class = None
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definitions."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions."""
        # Skip private functions for now (could be made configurable)
        if node.name.startswith('_') and not node.name.startswith('__'):
            self.generic_visit(node)
            return
            
        self.total_functions += 1
        
        # Check if function has return type annotation
        has_return_annotation = node.returns is not None
        
        # Check if all arguments have type annotations
        has_arg_annotations = True
        for arg in node.args.args:
            if arg.annotation is None and arg.arg != 'self':
                has_arg_annotations = False
                break
        
        # Function is considered typed if it has both return and argument annotations
        if has_return_annotation and has_arg_annotations:
            self.typed_functions += 1
        else:
            func_name = node.name
            if self.current_class:
                func_name = f"{self.current_class}.{func_name}"
            
            issues = []
            if not has_return_annotation:
                issues.append("missing return type")
            if not has_arg_annotations:
                issues.append("missing argument types")
            
            self.missing_annotations.append(f"{func_name}: {', '.join(issues)}")
        
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definitions."""
        # Treat async functions the same as regular functions
        self.visit_FunctionDef(node)


def analyze_file(file_path: Path) -> TypeAnalysis:
    """Analyze a single Python file for type annotation coverage."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        analyzer = TypeCoverageAnalyzer(str(file_path))
        analyzer.visit(tree)
        
        return TypeAnalysis(
            file_path=str(file_path),
            total_functions=analyzer.total_functions,
            typed_functions=analyzer.typed_functions,
            missing_annotations=analyzer.missing_annotations
        )
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return TypeAnalysis(str(file_path), 0, 0, [])


def analyze_directory(directory: Path) -> List[TypeAnalysis]:
    """Analyze all Python files in a directory recursively."""
    analyses = []
    
    for file_path in directory.rglob("*.py"):
        # Skip test files and __pycache__
        if "__pycache__" in str(file_path) or "/tests/" in str(file_path):
            continue
            
        analysis = analyze_file(file_path)
        if analysis.total_functions > 0:  # Only include files with functions
            analyses.append(analysis)
    
    return analyses


def print_coverage_report(analyses: List[TypeAnalysis], show_details: bool = False) -> None:
    """Print a comprehensive type coverage report."""
    total_functions = sum(a.total_functions for a in analyses)
    total_typed = sum(a.typed_functions for a in analyses)
    
    if total_functions == 0:
        print("No functions found to analyze.")
        return
    
    overall_coverage = (total_typed / total_functions) * 100
    
    print("=" * 80)
    print("SPACETIMEDB PYTHON SDK TYPE COVERAGE REPORT")
    print("=" * 80)
    print(f"Overall Type Coverage: {overall_coverage:.1f}% ({total_typed}/{total_functions})")
    print()
    
    # Sort analyses by coverage percentage (lowest first to highlight issues)
    analyses_sorted = sorted(analyses, key=lambda a: (a.typed_functions / a.total_functions) if a.total_functions > 0 else 0)
    
    print("PER-FILE BREAKDOWN:")
    print("-" * 80)
    print(f"{'File':<50} {'Coverage':<10} {'Typed/Total':<12}")
    print("-" * 80)
    
    for analysis in analyses_sorted:
        if analysis.total_functions > 0:
            coverage = (analysis.typed_functions / analysis.total_functions) * 100
            file_name = Path(analysis.file_path).name
            print(f"{file_name:<50} {coverage:>6.1f}% {analysis.typed_functions:>5}/{analysis.total_functions:<5}")
    
    if show_details:
        print("\nDETAILED MISSING ANNOTATIONS:")
        print("-" * 80)
        for analysis in analyses_sorted:
            if analysis.missing_annotations:
                print(f"\n{analysis.file_path}:")
                for missing in analysis.missing_annotations:
                    print(f"  - {missing}")
    
    print()
    print("SUMMARY STATISTICS:")
    print("-" * 40)
    print(f"Files analyzed: {len(analyses)}")
    print(f"Total functions: {total_functions}")
    print(f"Typed functions: {total_typed}")
    print(f"Missing annotations: {total_functions - total_typed}")
    print(f"Target coverage (95%): {0.95 * total_functions:.0f} functions")
    print(f"Functions needed for 95%: {max(0, int(0.95 * total_functions) - total_typed)}")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1])
    else:
        target_dir = Path("src/spacetimedb_sdk")
    
    if not target_dir.exists():
        print(f"Directory {target_dir} does not exist.")
        sys.exit(1)
    
    show_details = "--details" in sys.argv
    
    print(f"Analyzing type coverage in: {target_dir}")
    print("Scanning Python files...")
    
    analyses = analyze_directory(target_dir)
    print_coverage_report(analyses, show_details)


if __name__ == "__main__":
    main()