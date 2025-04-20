import os
import ast
import json
from collections import defaultdict
from typing import Any, Dict, List, DefaultDict, Union, Optional
import matplotlib.pyplot as plt
import networkx as nx



def analyze_python_code(path: str) -> Dict[str, Any]:
    """
    Analyze Python code at the given path - either a single file or directory.
    """
    if os.path.isfile(path) and path.endswith('.py'):
        return analyze_python_file(path)
    elif os.path.isdir(path):
        return analyze_python_directory(path)
    else:
        raise ValueError(f"Path must be a Python file or directory: {path}")


def analyze_python_file(filepath: str) -> Dict[str, Any]:
    """
    Analyze a single Python file comprehensively.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source: str = f.read()
        tree: ast.AST = ast.parse(source)
        lines: List[str] = source.splitlines()
    except Exception as e:
        return {
            'file_info': {
                'filename': os.path.basename(filepath),
                'path': filepath
            },
            'error': str(e)
        }

    imported: set = set()
    result: Dict[str, Any] = {
        'file_info': {
            'filename': os.path.basename(filepath),
            'path': filepath,
            'size_bytes': os.path.getsize(filepath),
            'line_count': len(lines)
        },
        'structure': {
            'imports': [],
            'classes': [],
            'functions': [],
            'variables': []
        },
        'metrics': {},
        'references': {},
        'unused_code': []
    }

    # ---- IMPORTS ----
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split('.')[0]
                imported.add(name)
                result['structure']['imports'].append({
                    'name': alias.name,
                    'alias': alias.asname,
                    'line': node.lineno,
                    'from_import': False
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                name = alias.asname or alias.name
                imported.add(name)
                result['structure']['imports'].append({
                    'module': module,
                    'name': alias.name,
                    'alias': alias.asname,
                    'line': node.lineno,
                    'from_import': True
                })

    # Collect definitions for reference tracking
    definitions: Dict[str, List[int]] = {}

    # ---- CLASSES & METHODS ----
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name not in imported:
            cls_name: str = node.name
            cls_entry: Dict[str, Any] = {
                'name': cls_name,
                'line_start': node.lineno,
                'docstring': ast.get_docstring(node) or '',
                'methods': [],
                'references': []
            }
            definitions.setdefault(cls_name, []).append(node.lineno)
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    m_name: str = child.name
                    methods_entry: Dict[str, Any] = {
                        'name': m_name,
                        'line': child.lineno,
                        'docstring': ast.get_docstring(child) or '',
                        'parameters': [arg.arg for arg in child.args.args],
                        'references': []
                    }
                    cls_entry['methods'].append(methods_entry)
                    definitions.setdefault(m_name, []).append(child.lineno)
            result['structure']['classes'].append(cls_entry)

    # ---- FUNCTIONS ----
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name not in imported:
            is_method = any(
                m['name'] == node.name and m['line'] == node.lineno
                for cls in result['structure']['classes'] for m in cls['methods']
            )
            if is_method:
                continue
            f_name: str = node.name
            func_entry: Dict[str, Any] = {
                'name': f_name,
                'line': node.lineno,
                'docstring': ast.get_docstring(node) or '',
                'parameters': [arg.arg for arg in node.args.args],
                'references': []
            }
            definitions.setdefault(f_name, []).append(node.lineno)
            result['structure']['functions'].append(func_entry)

    # ---- VARIABLES ----
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in imported:
                    v_name: str = target.id
                    var_entry: Dict[str, Any] = {
                        'name': v_name,
                        'line': target.lineno,
                        'references': []
                    }
                    definitions.setdefault(v_name, []).append(target.lineno)
                    result['structure']['variables'].append(var_entry)

    # ---- REFERENCE SCANNING ----
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            name: str = node.id
            if name in definitions and node.lineno not in definitions[name]:
                context: str = lines[node.lineno - 1].strip()
                ref_info: Dict[str, Union[int, str]] = {
                    'line': node.lineno,
                    'column': node.col_offset,
                    'context': context
                }
                result['references'].setdefault(name, []).append(ref_info)

    # ---- METRICS ----
    comp: DefaultDict[str, int] = defaultdict(int)

    def visit(n: ast.AST) -> None:
        if isinstance(n, (ast.If, ast.IfExp)):
            comp['conditionals'] += 1
        if isinstance(n, (ast.For, ast.While, ast.AsyncFor)):
            comp['loops'] += 1
        if isinstance(n, ast.Try):
            comp['exceptions'] += 1 + len(n.handlers)
        if isinstance(n, ast.BoolOp):
            comp['boolean_ops'] += 1
        if isinstance(n, ast.Call):
            comp['function_calls'] += 1
        for c in ast.iter_child_nodes(n):
            visit(c)

    visit(tree)
    result['metrics'] = {
        'conditional_count': comp.get('conditionals', 0),
        'loop_count': comp.get('loops', 0),
        'detailed_complexity': dict(comp),
        'complexity': 1 + comp.get('conditionals', 0) + comp.get('loops', 0)
                     + comp.get('exceptions', 0) + comp.get('boolean_ops', 0)
    }

    # ---- SUMMARY ----
    result['summary'] = {
        'class_count': len(result['structure']['classes']),
        'method_count': sum(len(c['methods']) for c in result['structure']['classes']),
        'function_count': len(result['structure']['functions']),
        'import_count': len(result['structure']['imports']),
        'variable_count': len(result['structure']['variables']),
        'unused_count': len(result.get('unused_code', []))
    }

    return result


def analyze_python_directory(
    directory: str,
    include_imports: bool = False,
    include_imported_code: bool = False,
    exclude_tests: bool = False
) -> Dict[str, Any]:
    """
    Analyze all Python files in a directory structure.
    Options:
      - include_imports: retain import details in file structures
      - include_imported_code: traverse vendor/virtualenv dirs
      - exclude_tests: skip test files and directories (paths or names starting with 'test')
    """
    ignore_dirs = {'.venv', 'venv', 'env', '__pycache__', '.git'}
    results: Dict[str, Any] = {
        'directory': directory,
        'files': [],
        'summary': defaultdict(int),
        'unused_code': []
    }
    for root, dirs, files in os.walk(directory):
        # Skip vendor dirs
        if not include_imported_code:
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
        # Skip test dirs
        if exclude_tests:
            dirs[:] = [d for d in dirs if not d.lower().startswith('test')]
        for file in files:
            if not file.endswith('.py'):
                continue
            # Skip test files
            if exclude_tests and file.lower().startswith('test_') or file.lower().endswith('_test.py'):
                continue
            file_path = os.path.join(root, file)
            file_result = analyze_python_file(file_path)
            if not include_imports:
                file_result['structure'].pop('imports', None)
                file_result['summary']['import_count'] = 0
            results['files'].append(file_result)
            for k, v in file_result['summary'].items():
                results['summary'][k] += v  # type: ignore

    total_files: int = len(results['files']) or 1
    total_complexity: int = sum(f['metrics'].get('complexity', 0) for f in results['files'])
    results['summary']['avg_complexity'] = round(total_complexity / total_files, 2)
    results['module_dependencies'] = find_module_dependencies(results['files'])
    return results


def find_module_dependencies(files: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    deps: Dict[str, List[str]] = {}
    for f in files:
        name = os.path.splitext(f['file_info']['filename'])[0]
        deps[name] = []
        for imp in f.get('structure', {}).get('imports', []):
            mod = imp.get('module', imp.get('name', '')).split('.')[0]
            if mod and mod != name and mod in deps and mod not in deps[name]:
                deps[name].append(mod)
    return deps


def generate_file_code_map(file_result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'filename': file_result['file_info']['filename'],
        'classes': [
            {
                'name': c['name'],
                'docstring': c['docstring'],
                'methods': [
                    { 'name': m['name'], 'docstring': m['docstring'], 'parameters': m['parameters'] }
                    for m in c.get('methods', [])
                ]
            }
            for c in file_result.get('structure', {}).get('classes', [])
        ],
        'functions': [
            { 'name': f['name'], 'docstring': f['docstring'], 'parameters': f['parameters'] }
            for f in file_result.get('structure', {}).get('functions', [])
        ],
        'variables': [v['name'] for v in file_result.get('structure', {}).get('variables', [])]
    }


def generate_code_map(results: Dict[str, Any]) -> Dict[str, Any]:
    if 'directory' in results:
        return { f['file_info']['filename']: generate_file_code_map(f) for f in results['files'] }
    else:
        return { results['file_info']['filename']: generate_file_code_map(results) }


def show_code_structure(results):
    for f in results['files']:
        fn = f['file_info']['filename']
        print(fn)
        # Classes & their methods
        for cls in f['structure'].get('classes', []):
            print(f"  📦 {cls['name']}")
            for m in cls['methods']:
                print(f"    └─ {m['name']}()")
        # Standalone functions
        for fnc in f['structure'].get('functions', []):
            print(f"  🔧 {fnc['name']}()")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Analyze Python code')
    parser.add_argument('path', help='Path to analyze')
    parser.add_argument('--json', '-j', help='Output JSON')
    parser.add_argument(
        '--include-imports',
        action='store_true',
        help='Include import statements in output'
    )
    parser.add_argument(
        '--include-imported-code',
        action='store_true',
        help='Include vendor/imported code directories in directory scan'
    )
    parser.add_argument(
        '--exclude-tests',
        action='store_true',
        help='Exclude test files and directories from scan'
    )
    args = parser.parse_args()

    if os.path.isdir(args.path):
        res = analyze_python_directory(
            args.path,
            include_imports=args.include_imports,
            include_imported_code=args.include_imported_code,
            exclude_tests=args.exclude_tests
        )
    else:
        res = analyze_python_file(args.path)
    print(res)
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=2)
