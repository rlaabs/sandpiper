import argparse
from .analyzer import analyze_codebase

def main():
    parser = argparse.ArgumentParser(
        description='Analyze a Python codebase to count references for functions and classes using Jedi.'
    )
    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Directory of the codebase to analyze (default: current directory)'
    )
    args = parser.parse_args()

    results = analyze_codebase(args.directory)
    # Get the maximum lengths for proper alignment
    max_name_length = max((len(name) for name in results.keys()), default=0)
    max_count_length = max((len(str(count)) for count in results.values()), default=0)
    
    print("\nFunction & Class Reference Analysis")
    print("=" * 50)
    print(f"{'Name':<{max_name_length}} | {'References':>{max_count_length}}")
    print("-" * max_name_length + "-+-" + "-" * max_count_length)
    
    for name, count in sorted(results.items(), key=lambda x: x[1], reverse=True):
        print(f"{name:<{max_name_length}} | {count:>{max_count_length}}")
    
    print("\nTotal items analyzed:", len(results))

if __name__ == "__main__":
    main()