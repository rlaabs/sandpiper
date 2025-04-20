import os
import ast
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, DefaultDict, Union

def analyze_python_code(path:str) -> Dict[str, Any]:
    """
    Analyze Python code at the given path - either a single file or directory.
    """
    if os.path.isfile(path) and path.endswith('.py'):
        return analyze_python_file(path)
    elif os.path.isdir(path):
        return analyze_python_directory(path)
    else:
        raise ValueError(f"Path must be a Python file or directory: {path}")


def analyze_python_file(filepath:str) -> Dict[str, Any]:
    """
    Analyze a single Python file comprehensively.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        lines = source.splitlines()
    except Exception as e:
        return {'file_info': {'filename': os.path.basename(filepath), 'path': filepath}, 'error': str(e)}

    imported = set()
    result = {
        'file_info': {
            'filename': os.path.basename(filepath),
            'path': filepath,
            'size_bytes': os.path.getsize(filepath),
            'line_count': len(lines)
        },
        'structure': {'imports': [], 'classes': [], 'functions': [], 'variables': []},
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
    definitions = {}

    # ---- CLASSES & METHODS ----
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name not in imported:
            cls_name = node.name
            cls_entry = {
                'name': cls_name,
                'line_start': node.lineno,
                'docstring': ast.get_docstring(node) or '',
                'methods': [],
                'references': []
            }
            definitions.setdefault(cls_name, []).append(node.lineno)
            # Methods
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    m_name = child.name
                    methods_entry = {
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
            # skip methods
            is_method = False
            for cls in result['structure']['classes']:
                if any(m['name'] == node.name and m['line'] == node.lineno for m in cls['methods']):
                    is_method = True
                    break
            if is_method:
                continue
            f_name = node.name
            func_entry = {
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
                    v_name = target.id
                    var_entry = {'name': v_name, 'line': target.lineno, 'references': []}
                    definitions.setdefault(v_name, []).append(target.lineno)
                    result['structure']['variables'].append(var_entry)

    # ---- REFERENCE SCANNING ----
    # Traverse AST and record Name nodes that refer to definitions
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            name = node.id
            if name in definitions:
                # skip definition occurrence
                if node.lineno in definitions[name]:
                    continue
                context = lines[node.lineno-1].strip()
                ref_info = {'line': node.lineno, 'column': node.col_offset, 'context': context}
                # global references
                result['references'].setdefault(name, []).append(ref_info)
                # structure-level
                # classes
                for cls in result['structure']['classes']:
                    if cls['name'] == name:
                        cls['references'].append(ref_info)
                    for m in cls['methods']:
                        if m['name'] == name:
                            m['references'].append(ref_info)
                # functions
                for f in result['structure']['functions']:
                    if f['name'] == name:
                        f['references'].append(ref_info)
                # variables
                for v in result['structure']['variables']:
                    if v['name'] == name:
                        v['references'].append(ref_info)

    # ---- METRICS ----
    comp = defaultdict(int)
    def visit(n):
        if isinstance(n, (ast.If, ast.IfExp)): comp['conditionals'] += 1
        if isinstance(n, (ast.For, ast.While, ast.AsyncFor)): comp['loops'] += 1
        if isinstance(n, ast.Try): comp['exceptions'] += 1 + len(n.handlers)
        if isinstance(n, ast.BoolOp): comp['boolean_ops'] += 1
        if isinstance(n, ast.Call): comp['function_calls'] += 1
        for c in ast.iter_child_nodes(n): visit(c)
    visit(tree)
    total_cond = comp['conditionals']
    total_loops = comp['loops']
    total_ex = comp['exceptions']
    total_bool = comp['boolean_ops']
    result['metrics'] = {
        'conditional_count': total_cond,
        'loop_count': total_loops,
        'detailed_complexity': dict(comp),
        'complexity': 1 + total_cond + total_loops + total_ex + total_bool
    }

    # ---- SUMMARY ----
    result['summary'] = {
        'class_count': len(result['structure']['classes']),
        'method_count': sum(len(c['methods']) for c in result['structure']['classes']),
        'function_count': len(result['structure']['functions']),
        'import_count': len(result['structure']['imports']),
        'variable_count': len(result['structure']['variables']),
        'unused_count': len(result['unused_code'])
    }

    return result


def analyze_python_directory(directory):
    results = {'directory': directory, 'files': [], 'summary': defaultdict(int), 'unused_code': []}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                res = analyze_python_file(os.path.join(root, file))
                results['files'].append(res)
                # aggregate summaries
                for k in ('class_count','method_count','function_count','import_count','variable_count','unused_count'):
                    results['summary'][k] += res['summary'].get(k, 0)
    count = len(results['files']) or 1
    results['summary']['avg_complexity'] = round(sum(f['metrics']['complexity'] for f in results['files'])/count,2)
    results['summary']['avg_docstring_coverage'] = round(sum(f['metrics'].get('docstring_coverage',0) for f in results['files'])/count,2)
    results['module_dependencies'] = find_module_dependencies(results['files'])
    return results


def find_module_dependencies(files):
    deps = {}
    for f in files:
        name = os.path.splitext(f['file_info']['filename'])[0]
        deps[name] = []
        for imp in f['structure']['imports']:
            mod = imp.get('module', imp['name']).split('.')[0]
            if mod != name and mod in deps and mod not in deps[name]:
                deps[name].append(mod)
    return deps


def generate_file_code_map(file_result):
    """
    Produce a high-level summary of a single file's structure for LLM consumption.
    """
    return {
        'filename': file_result['file_info']['filename'],
        'classes': [
            {
                'name': c['name'], 'docstring': c['docstring'],
                'methods': [{ 'name': m['name'], 'docstring': m['docstring'], 'parameters': m['parameters'] } for m in c['methods']]
            } for c in file_result['structure']['classes']
        ],
        'functions': [
            { 'name': f['name'], 'docstring': f['docstring'], 'parameters': f['parameters'] }
            for f in file_result['structure']['functions']
        ],
        'variables': [v['name'] for v in file_result['structure']['variables']]
    }


def generate_code_map(results):
    """
    Produce an aggregated code map across all analyzed files.
    """
    if 'directory' in results:
        return { f['file_info']['filename']: generate_file_code_map(f) for f in results['files'] }
    else:
        return { results['file_info']['filename']: generate_file_code_map(results) }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Analyze Python code')
    parser.add_argument('path', help='Path to analyze')
    parser.add_argument('--json','-j',help='Output JSON')
    args = parser.parse_args()
    res = analyze_python_code(args.path)
    print(res)
    if args.json:
        with open(args.json,'w',encoding='utf-8') as f:
            json.dump(res,f,indent=2)
