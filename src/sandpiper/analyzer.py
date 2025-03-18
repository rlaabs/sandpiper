import os
import jedi

def analyze_file(filepath: str) -> dict:
    """
    Analyze a single Python file and return a dictionary mapping
    function and class definitions (using their full names when available)
    to their reference counts.
    """
    definitions = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        raise Exception(f"Error reading {filepath}: {e}")
    
    script = jedi.Script(source, path=filepath)

    # Extract definitions (classes, functions, etc.)
    for d in script.get_names(definitions=True, all_scopes=True):
        key = d.full_name or d.name
        definitions.setdefault(key, 0)
    
    # Count references for each definition in the file.
    for name in script.get_names(all_scopes=True):
        key = name.full_name or name.name
        if key in definitions:
            definitions[key] += 1
    
    return definitions

def analyze_codebase(directory: str) -> dict:
    """
    Recursively analyze all Python files in the given directory.
    Returns a dictionary combining the reference counts for definitions
    across all files.
    """
    combined_definitions = {}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    file_definitions = analyze_file(filepath)
                    for key, count in file_definitions.items():
                        combined_definitions[key] = combined_definitions.get(key, 0) + count
                except Exception as e:
                    print(f"Skipping {filepath} due to error: {e}")
                    continue
    return combined_definitions


    
 