#!/usr/bin/env python3
"""
Find Agent Imports - Migration Helper
=======================================

Scans the codebase to find all files that import from the agents folder.
Helps identify what needs to be updated during code migration.

Usage:
    python scripts/database/find_agent_imports.py
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

def find_agent_imports(root_dir: str = "app") -> Dict[str, List[Tuple[int, str]]]:
    """
    Find all files that import from agents folder
    
    Returns:
        Dict mapping file paths to list of (line_number, line_content) tuples
    """
    results = {}
    root_path = Path(root_dir)
    
    # Patterns to match agent imports
    patterns = [
        r'from\s+app\.agents',
        r'from\s+agents\.',
        r'import\s+.*agents',
        r'from\s+.*agents\s+import',
    ]
    
    # File extensions to check
    extensions = {'.py', '.pyx', '.pyi'}
    
    for file_path in root_path.rglob('*'):
        if file_path.suffix not in extensions:
            continue
            
        # Skip __pycache__ and virtual environments
        if '__pycache__' in str(file_path) or 'venv' in str(file_path) or 'node_modules' in str(file_path):
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                matches = []
                
                for line_num, line in enumerate(lines, 1):
                    for pattern in patterns:
                        if re.search(pattern, line):
                            matches.append((line_num, line.strip()))
                            break
                
                if matches:
                    results[str(file_path)] = matches
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    return results

def print_results(results: Dict[str, List[Tuple[int, str]]]):
    """Print results in a readable format"""
    if not results:
        print("✅ No agent imports found!")
        return
    
    print(f"\n📋 Found {len(results)} file(s) with agent imports:\n")
    print("=" * 80)
    
    for file_path, matches in sorted(results.items()):
        print(f"\n📄 {file_path}")
        print("-" * 80)
        for line_num, line_content in matches:
            print(f"  Line {line_num:4d}: {line_content}")
    
    print("\n" + "=" * 80)
    print(f"\n📊 Summary: {len(results)} files need to be updated")

def generate_migration_commands(results: Dict[str, List[Tuple[int, str]]]):
    """Generate sed/awk commands for automated replacement"""
    print("\n🔧 Suggested replacement commands:\n")
    
    replacements = [
        (r'from app\.agents import', 'from app.services.agents import'),
        (r'from app\.agents\.', 'from app.services.agents.'),
        (r'from agents\.', 'from services.agents.'),
    ]
    
    for old_pattern, new_pattern in replacements:
        print(f"# Replace: {old_pattern} → {new_pattern}")
        print(f"# sed -i 's/{old_pattern}/{new_pattern}/g' <file>")
        print()

if __name__ == "__main__":
    print("🔍 Searching for agent imports...")
    results = find_agent_imports()
    print_results(results)
    generate_migration_commands(results)
    
    # Save to file
    output_file = "agent_imports_audit.txt"
    with open(output_file, 'w') as f:
        f.write("Agent Imports Audit\n")
        f.write("=" * 80 + "\n\n")
        for file_path, matches in sorted(results.items()):
            f.write(f"{file_path}\n")
            f.write("-" * 80 + "\n")
            for line_num, line_content in matches:
                f.write(f"  Line {line_num:4d}: {line_content}\n")
            f.write("\n")
    
    print(f"\n💾 Results saved to: {output_file}")

