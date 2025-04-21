import argparse
import json
import sys

from sandpiper.analyzer import analyze_python_code, generate_file_code_map, generate_code_map, show_code_structure

def main():
    parser = argparse.ArgumentParser(description='Analyze Python code')
    parser.add_argument(
        'path',
        help='Path to a Python file or directory to analyze'
    )
    parser.add_argument(
        '--json',
        dest='json_file',
        metavar='FILE',
        help='Write output as JSON to this file'
    )
    parser.add_argument(
        '--include-imports',
        action='store_true',
        default=False,
        help='Include import statements in output'
    )
    parser.add_argument(
        '--include-imported-code',
        action='store_true',
        default=False,
        help='Include vendor/imported code directories in directory scan'
    )
    parser.add_argument(
        '--exclude-tests',
        action='store_true',
        help='Exclude test files and directories from scan'
    )
    # Add new command group
    output_group = parser.add_argument_group('output formats')
    output_group.add_argument(
        '--code-map',
        action='store_true',
        help='Generate a simplified code map of the analyzed code'
    )
    output_group.add_argument(
        '--file-code-map',
        action='store_true',
        help='Generate a simplified code map for a single file'
    )
    output_group.add_argument(
        '--show-structure',
        action='store_true',
        help='Display the code structure in a readable format'
    )
    args = parser.parse_args()

    # Delegate to analyzer
    try:
        result = analyze_python_code(
            args.path,
            include_imports=args.include_imports,
            include_imported_code=args.include_imported_code,
            exclude_tests=args.exclude_tests
        )
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)

    # Process results based on requested output format
    if args.show_structure:
        # Display the structure directly to stdout
        show_code_structure(result)
        return
    
    # Apply transformations if requested
    if args.file_code_map and 'file_info' in result:
        # Single file mode
        result = generate_file_code_map(result)
    elif args.code_map:
        # Directory or single file mode
        result = generate_code_map(result)

    # Serialize to JSON
    output = json.dumps(result, indent=2)

    # Write to file or stdout
    try:
        if args.json_file:
            with open(args.json_file, 'w', encoding='utf-8') as f:
                f.write(output)
        else:
            print(output)
    except IOError as e:
        sys.stderr.write(f"Error writing output: {e}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()