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
    print("Function & Class References:")
    for name, count in results.items():
        print(f"{name}: {count}")

if __name__ == "__main__":
    main()