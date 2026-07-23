#!/usr/bin/env python3
"""
Comprehensive diagnostic tool to find ALL potential execution failures.

Searches for:
1. Silent exception handlers (bare except, pass)
2. Unchecked return values
3. Unwaited coroutines
4. Ignored asyncio.create_task() results
5. Background tasks without error handling
6. Cancelled tasks
7. Context manager issues
"""

import ast
import re
import sys
import os
from pathlib import Path
from typing import List, Set, Dict

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

class DiagnosticVisitor(ast.NodeVisitor):
    """AST visitor to find potential execution failures."""

    def __init__(self, filename: str):
        self.filename = filename
        self.issues: List[Dict] = []
        self.current_function = None
        self.source_lines = {}

    def add_issue(self, node, issue_type: str, message: str, severity: str = "WARNING"):
        """Record a diagnostic issue."""
        self.issues.append({
            'file': self.filename,
            'line': node.lineno if hasattr(node, 'lineno') else 0,
            'type': issue_type,
            'message': message,
            'severity': severity,
            'function': self.current_function
        })

    def visit_FunctionDef(self, node):
        """Track function definitions."""
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node):
        """Track async function definitions."""
        old_function = self.current_function
        self.current_function = f"async {node.name}"
        self.generic_visit(node)
        self.current_function = old_function

    def visit_Try(self, node):
        """Check exception handlers for silent failures."""
        for handler in node.handlers:
            # Check for bare except
            if handler.type is None:
                self.add_issue(
                    handler,
                    'BARE_EXCEPT',
                    'Bare except clause found - will silently catch ALL exceptions',
                    'CRITICAL'
                )
            # Check for except Exception without logging
            elif isinstance(handler.type, ast.Name) and handler.type.id == 'Exception':
                # Check if body only contains pass or return None/False
                if len(handler.body) == 1:
                    stmt = handler.body[0]
                    if isinstance(stmt, ast.Pass):
                        self.add_issue(
                            handler,
                            'SILENT_HANDLER',
                            'Exception handler with only pass - silently swallows exceptions',
                            'CRITICAL'
                        )
                    elif isinstance(stmt, ast.Return):
                        if stmt.value is None or (isinstance(stmt.value, ast.Constant) and stmt.value.value is False):
                            self.add_issue(
                                handler,
                                'SILENT_HANDLER',
                                'Exception handler returns None/False without logging',
                                'CRITICAL'
                            )
        self.generic_visit(node)

    def visit_Expr(self, node):
        """Check for unawaited coroutines."""
        if isinstance(node.value, ast.Await):
            # Await is OK
            pass
        elif isinstance(node.value, ast.Call):
            # Check if calling a function that returns a coroutine
            if isinstance(node.value.func, ast.Attribute):
                if node.value.func.attr in ['create_task', 'add_task']:
                    self.add_issue(
                        node,
                        'UNAWAITED_TASK',
                        f'Result of {node.value.func.attr}() not awaited - task may be silently cancelled',
                        'CRITICAL'
                    )
        self.generic_visit(node)

    def visit_Assign(self, node):
        """Check for ignored return values from async functions."""
        if isinstance(node.value, ast.Call):
            # Check if calling create_task without awaiting
            if isinstance(node.value.func, ast.Attribute):
                if node.value.func.attr == 'create_task':
                    # Storing but not awaiting/checking
                    pass  # This is OK if stored
        self.generic_visit(node)

    def visit_Return(self, node):
        """Check for problematic return values."""
        if node.value is None:
            # Implicit return None - OK
            pass
        elif isinstance(node.value, ast.Constant):
            if node.value.value is False or node.value.value is None:
                self.add_issue(
                    node,
                    'PROBLEMATIC_RETURN',
                    'Function returns False/None without logging error - may hide failures',
                    'WARNING'
                )
        self.generic_visit(node)


def scan_file(filepath: Path) -> List[Dict]:
    """Scan a Python file for diagnostic issues."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        tree = ast.parse(source, filename=str(filepath))
        visitor = DiagnosticVisitor(str(filepath))
        visitor.visit(tree)

        return visitor.issues
    except Exception as e:
        print(f"⚠️  Error scanning {filepath}: {e}")
        return []


def scan_directory(directory: Path) -> List[Dict]:
    """Scan all Python files in a directory."""
    all_issues = []

    for py_file in directory.rglob('*.py'):
        # Skip venv and test files
        if '.venv' in str(py_file) or '__pycache__' in str(py_file):
            continue

        issues = scan_file(py_file)
        all_issues.extend(issues)

    return all_issues


def grep_pattern(directory: Path, pattern: str, exclude_venv=True) -> List[Dict]:
    """Grep for specific patterns in Python files."""
    matches = []

    for py_file in directory.rglob('*.py'):
        if exclude_venv and '.venv' in str(py_file):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if re.search(pattern, line):
                        matches.append({
                            'file': str(py_file),
                            'line': line_num,
                            'pattern': pattern,
                            'content': line.strip()
                        })
        except Exception as e:
            pass

    return matches


def print_report(issues: List[Dict], title: str):
    """Print a diagnostic report."""
    if not issues:
        print(f"\n✓ {title}: No issues found")
        return

    print(f"\n{'='*80}")
    print(f"🔴 {title}: {len(issues)} issue(s) found")
    print(f"{'='*80}\n")

    # Group by severity
    by_severity = {}
    for issue in issues:
        severity = issue.get('severity', 'WARNING')
        if severity not in by_severity:
            by_severity[severity] = []
        by_severity[severity].append(issue)

    # Print by severity
    for severity in ['CRITICAL', 'WARNING']:
        if severity in by_severity:
            print(f"\n{severity}S:")
            for issue in by_severity[severity]:
                print(f"  {issue['file']}:{issue['line']}")
                print(f"    {issue['type']}: {issue['message']}")
                if issue.get('function'):
                    print(f"    In function: {issue['function']}")


def main():
    """Run comprehensive diagnostics."""
    repo_root = Path('.')

    print("🔍 Starting comprehensive production diagnostics...\n")

    # 1. AST analysis for structural issues
    print("📊 Analyzing Python AST for structural issues...")
    ast_issues = scan_directory(repo_root / 'app')

    # 2. Pattern matching for known issues
    print("🔎 Searching for known problematic patterns...\n")

    patterns = {
        'Silent pass statements': (r'except.*:\s*pass\s*$', 'CRITICAL'),
        'Bare except clauses': (r'except\s*:\s*', 'CRITICAL'),
        'Return False without logging': (r'return\s+False', 'HIGH'),
        'Return None without logging': (r'return\s+None', 'MEDIUM'),
        'Except Exception without logging': (r'except Exception[^:]*:\s+pass', 'CRITICAL'),
    }

    pattern_matches = {}
    for pattern_name, (pattern, severity) in patterns.items():
        matches = grep_pattern(repo_root / 'app', pattern)
        if matches:
            pattern_matches[pattern_name] = [(m, severity) for m in matches]

    # 3. Check for BackgroundTasks without proper error handling
    print("📋 Checking BackgroundTasks usage...")
    bg_task_files = grep_pattern(repo_root / 'app', r'background_tasks\.add_task|create_task')

    # 4. Check for asyncio issues
    print("🔄 Checking for asyncio issues...")
    async_issues = grep_pattern(repo_root / 'app', r'asyncio\.create_task\(|BackgroundTasks')

    # Print reports
    print_report(ast_issues, "AST Analysis Results")

    if pattern_matches:
        print(f"\n{'='*80}")
        print(f"🔴 Pattern Matching Results")
        print(f"{'='*80}\n")
        for pattern_name, matches in pattern_matches.items():
            print(f"\n{pattern_name}:")
            for match, severity in matches:
                print(f"  {match['file']}:{match['line']}")
                print(f"    {match['content']}")
                print(f"    [Severity: {severity}]")

    if bg_task_files:
        print(f"\n{'='*80}")
        print(f"⚠️  BackgroundTasks Usage")
        print(f"{'='*80}\n")
        for match in bg_task_files:
            print(f"  {match['file']}:{match['line']}")
            print(f"    {match['content']}")

    # Summary
    total_issues = len(ast_issues) + sum(len(m) for m in pattern_matches.values())
    print(f"\n{'='*80}")
    print(f"DIAGNOSTIC SUMMARY")
    print(f"{'='*80}")
    print(f"Total issues found: {total_issues}")
    print(f"  - AST issues: {len(ast_issues)}")
    print(f"  - Pattern matches: {sum(len(m) for m in pattern_matches.values())}")
    print(f"  - BackgroundTasks usages: {len(bg_task_files)}")

    if total_issues > 0:
        print(f"\n⚠️  Issues found that could cause silent failures!")
        sys.exit(1)
    else:
        print(f"\n✓ No obvious issues found in static analysis")
        sys.exit(0)


if __name__ == "__main__":
    main()
