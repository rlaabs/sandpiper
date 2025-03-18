import textwrap
import pytest
from sandpiper.analyzer import analyze_file, analyze_codebase

def test_analyze_file(tmp_path):
    file_content = textwrap.dedent("""\
        class MyClass:
            def method1(self):
                return self.method2()

            def method2(self):
                pass

        def my_function():
            return MyClass()

        my_var = MyClass()
        another_call = my_function()
    """)
    file_path = tmp_path / "test_file.py"
    file_path.write_text(file_content)
    result = analyze_file(str(file_path))
    # Jedi may return full names (e.g., "test_file.MyClass") so we search for substrings.
    assert any("MyClass" in key for key in result)
    assert any("my_function" in key for key in result)
    assert any("method1" in key for key in result)
    assert any("method2" in key for key in result)


def test_analyze_codebase(tmp_path):
    # Create two temporary Python files in the temporary directory.
    file_content1 = textwrap.dedent("""\
        def func_a():
            pass

        def func_b():
            return func_a()
    """)
    file_content2 = textwrap.dedent("""\
        class ClassA:
            def method_a(self):
                pass
    """)
    file1 = tmp_path / "module1.py"
    file2 = tmp_path / "module2.py"
    file1.write_text(file_content1)
    file2.write_text(file_content2)

    result = analyze_codebase(str(tmp_path))
    # Check that definitions from both files are included in the results.
    assert any("func_a" in key for key in result)
    assert any("func_b" in key for key in result)
    assert any("ClassA" in key for key in result)
    # Ensure that nested definitions (methods) are captured.
    assert any("method_a" in key for key in result)