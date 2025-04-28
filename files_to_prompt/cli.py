import ast
import os
import sys
from fnmatch import fnmatch

import click

global_index = 1

EXT_TO_LANG = {
    "py": "python",
    "c": "c",
    "cpp": "cpp",
    "java": "java",
    "js": "javascript",
    "ts": "typescript",
    "html": "html",
    "css": "css",
    "xml": "xml",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "sh": "bash",
    "rb": "ruby",
}

def extract_signatures_and_docstrings(file_path):
    """Extract function signatures and docstrings from a Python file."""
    try:
        with open(file_path, 'r') as f:
            source = f.read()
        
        # Replace tabs with spaces to normalize indentation
        source = source.replace('\t', '    ')
        module = ast.parse(source)
        source_lines = source.splitlines()
        
        # Function to extract the signature from source lines with proper indentation
        def get_signature(node, parent_indentation=0):
            line_index = node.lineno - 1  # AST line numbers are 1-based
            
            # Find the complete signature (handle multi-line signatures)
            line = source_lines[line_index]
            
            # Get the base indentation level of the first line
            # Find leading whitespace in the current line
            current_indentation = len(line) - len(line.lstrip())
            
            # For the first line in a method, we'll use the parent_indentation + 4
            if parent_indentation > 0:
                first_line = ' ' * parent_indentation + line.lstrip()
            else:
                first_line = line
            
            signature_lines = [first_line]
            
            # Keep adding lines until we find the closing colon
            while not signature_lines[-1].rstrip().endswith(':'):
                line_index += 1
                if line_index >= len(source_lines):
                    break  # Avoid index errors
                
                next_line = source_lines[line_index]
                
                # For continuation lines in a method signature, maintain alignment with opening parenthesis
                if parent_indentation > 0:
                    # Find the position of the first opening parenthesis in the signature
                    first_line_stripped = first_line.lstrip()
                    paren_pos = first_line_stripped.find('(')
                    if paren_pos != -1:
                        # Calculate the indentation needed to align with the opening parenthesis
                        align_pos = parent_indentation + paren_pos + 1  # +1 for the character after '('
                        next_line_content = next_line.lstrip()
                        next_line = ' ' * align_pos + next_line_content
                    else:
                        # If no opening parenthesis, use consistent indentation
                        next_line = ' ' * (parent_indentation + 4) + next_line.lstrip()
                
                signature_lines.append(next_line)
            
            return '\n'.join(signature_lines)
        
        # Function to normalize docstring indentation
        def normalize_docstring(docstring, indentation=0):
            if not docstring:
                return None
                
            lines = docstring.splitlines()
            
            # If only one line, return it with proper indentation
            if len(lines) == 1:
                return docstring
                
            # For multi-line docstrings, normalize the indentation
            # First, find the minimum indentation of non-empty lines after the first
            min_indent = float('inf')
            for line in lines[1:]:
                # Skip empty lines
                if line.strip():
                    curr_indent = len(line) - len(line.lstrip())
                    min_indent = min(min_indent, curr_indent)
            
            # If no non-empty lines were found, return the original
            if min_indent == float('inf'):
                min_indent = 0
                
            # Create normalized lines with proper indentation
            normalized = [lines[0]]  # First line stays as is
            for line in lines[1:]:
                if line.strip():  # Non-empty line
                    # Remove the common indentation and add the desired indentation
                    normalized.append(' ' * indentation + line[min_indent:])
                else:  # Empty line
                    normalized.append('')
                    
            return '\n'.join(normalized)
        
        results = []
        
        # Process all top-level function and class definitions
        for node in module.body:
            if isinstance(node, ast.FunctionDef):
                # Extract function signature from source
                signature = get_signature(node)
                
                # Get docstring if available
                docstring = ast.get_docstring(node)
                if docstring:
                    docstring = normalize_docstring(docstring, 4)
                    results.append(f"{signature}\n    \"\"\"{docstring}\"\"\"")
                else:
                    results.append(signature)
            
            elif isinstance(node, ast.ClassDef):
                # Extract class signature from source
                class_sig = get_signature(node)
                
                # Get class docstring if available
                class_docstring = ast.get_docstring(node)
                if class_docstring:
                    class_docstring = normalize_docstring(class_docstring, 4)
                    class_entry = f"{class_sig}\n    \"\"\"{class_docstring}\"\"\""
                else:
                    class_entry = class_sig
                
                results.append(class_entry)
                
                # Process class methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        # Extract method signature from source with 4-space indentation
                        method_sig = get_signature(item, 4)
                        
                        # Get method docstring if available
                        method_docstring = ast.get_docstring(item)
                        if method_docstring:
                            method_docstring = normalize_docstring(method_docstring, 8)
                            results.append(f"{method_sig}\n        \"\"\"{method_docstring}\"\"\"")
                        else:
                            results.append(f"{method_sig}")
        
        return "\n\n".join(results)
    except Exception as e:
        return f"Error extracting signatures from {file_path}: {str(e)}"

def should_ignore(path, gitignore_rules):
    for rule in gitignore_rules:
        if fnmatch(os.path.basename(path), rule):
            return True
        if os.path.isdir(path) and fnmatch(os.path.basename(path) + "/", rule):
            return True
    return False


def read_gitignore(path):
    gitignore_path = os.path.join(path, ".gitignore")
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r") as f:
            return [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    return []


def add_line_numbers(content):
    lines = content.splitlines()

    padding = len(str(len(lines)))

    numbered_lines = [f"{i + 1:{padding}}  {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def print_path(writer, path, content, cxml, markdown, line_numbers):
    if cxml:
        print_as_xml(writer, path, content, line_numbers)
    elif markdown:
        print_as_markdown(writer, path, content, line_numbers)
    else:
        print_default(writer, path, content, line_numbers)


def print_default(writer, path, content, line_numbers):
    writer(path)
    writer("---")
    if line_numbers:
        content = add_line_numbers(content)
    writer(content)
    writer("")
    writer("---")


def print_as_xml(writer, path, content, line_numbers):
    global global_index
    writer(f'<document index="{global_index}">')
    writer(f"<source>{path}</source>")
    writer("<document_content>")
    if line_numbers:
        content = add_line_numbers(content)
    writer(content)
    writer("</document_content>")
    writer("</document>")
    global_index += 1


def print_as_markdown(writer, path, content, line_numbers):
    # Extract the file extension for language detection
    file_path = path
    if " (signatures only)" in path:
        file_path = path.split(" (signatures only)")[0]
        
    lang = EXT_TO_LANG.get(file_path.split(".")[-1], "")
    
    # Figure out how many backticks to use
    backticks = "```"
    while backticks in content:
        backticks += "`"
    writer(path)
    writer(f"{backticks}{lang}")
    if line_numbers:
        content = add_line_numbers(content)
    writer(content)
    writer(f"{backticks}")


def process_path(
    path,
    extensions,
    include_hidden,
    ignore_files_only,
    ignore_gitignore,
    gitignore_rules,
    ignore_patterns,
    writer,
    claude_xml,
    markdown,
    line_numbers=False,
    signature_patterns=None,
):
    if signature_patterns is None:
        signature_patterns = []
    
    if os.path.isfile(path):
        try:
            # Check if this file should have only signatures extracted
            should_extract_signatures = any(fnmatch(path, pattern) for pattern in signature_patterns)
            
            if should_extract_signatures and path.endswith('.py'):
                content = extract_signatures_and_docstrings(path)
                print_path(writer, f"{path} (signatures only)", content, claude_xml, markdown, line_numbers)
            else:
                if should_extract_signatures and not path.endswith('.py'):
                    warning_message = f"Warning: Skipping signatures-only extraction for non-Python file {path}"
                    click.echo(click.style(warning_message, fg="red"), err=True)
                
                with open(path, "r") as f:
                    print_path(writer, path, f.read(), claude_xml, markdown, line_numbers)
        except UnicodeDecodeError:
            warning_message = f"Warning: Skipping file {path} due to UnicodeDecodeError"
            click.echo(click.style(warning_message, fg="red"), err=True)
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                files = [f for f in files if not f.startswith(".")]

            if not ignore_gitignore:
                gitignore_rules.extend(read_gitignore(root))
                dirs[:] = [
                    d
                    for d in dirs
                    if not should_ignore(os.path.join(root, d), gitignore_rules)
                ]
                files = [
                    f
                    for f in files
                    if not should_ignore(os.path.join(root, f), gitignore_rules)
                ]

            if ignore_patterns:
                if not ignore_files_only:
                    dirs[:] = [
                        d
                        for d in dirs
                        if not any(fnmatch(d, pattern) for pattern in ignore_patterns)
                    ]
                files = [
                    f
                    for f in files
                    if not any(fnmatch(f, pattern) for pattern in ignore_patterns)
                ]

            if extensions:
                files = [f for f in files if f.endswith(extensions)]

            for file in sorted(files):
                file_path = os.path.join(root, file)
                try:
                    # Check if this file should have only signatures extracted
                    should_extract_signatures = any(fnmatch(file_path, pattern) for pattern in signature_patterns)
                    
                    if should_extract_signatures and file_path.endswith('.py'):
                        content = extract_signatures_and_docstrings(file_path)
                        print_path(writer, f"{file_path} (signatures only)", content, claude_xml, markdown, line_numbers)
                    else:
                        if should_extract_signatures and not file_path.endswith('.py'):
                            warning_message = f"Warning: Skipping signatures-only extraction for non-Python file {file_path}"
                            click.echo(click.style(warning_message, fg="red"), err=True)
                        
                        with open(file_path, "r") as f:
                            print_path(writer, file_path, f.read(), claude_xml, markdown, line_numbers)
                except UnicodeDecodeError:
                    warning_message = f"Warning: Skipping file {file_path} due to UnicodeDecodeError"
                    click.echo(click.style(warning_message, fg="red"), err=True)


def read_paths_from_stdin(use_null_separator):
    if sys.stdin.isatty():
        # No ready input from stdin, don't block for input
        return []

    stdin_content = sys.stdin.read()
    if use_null_separator:
        paths = stdin_content.split("\0")
    else:
        paths = stdin_content.split()  # split on whitespace
    return [p for p in paths if p]


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("extensions", "-e", "--extension", multiple=True)
@click.option(
    "--include-hidden",
    is_flag=True,
    help="Include files and folders starting with .",
)
@click.option(
    "--ignore-files-only",
    is_flag=True,
    help="--ignore option only ignores files",
)
@click.option(
    "--ignore-gitignore",
    is_flag=True,
    help="Ignore .gitignore files and include all files",
)
@click.option(
    "ignore_patterns",
    "--ignore",
    multiple=True,
    default=[],
    help="List of patterns to ignore",
)
@click.option(
    "output_file",
    "-o",
    "--output",
    type=click.Path(writable=True),
    help="Output to a file instead of stdout",
)
@click.option(
    "claude_xml",
    "-c",
    "--cxml",
    is_flag=True,
    help="Output in XML-ish format suitable for Claude's long context window.",
)
@click.option(
    "markdown",
    "-m",
    "--markdown",
    is_flag=True,
    help="Output Markdown with fenced code blocks",
)
@click.option(
    "line_numbers",
    "-n",
    "--line-numbers",
    is_flag=True,
    help="Add line numbers to the output",
)
@click.option(
    "--null",
    "-0",
    is_flag=True,
    help="Use NUL character as separator when reading from stdin",
)
@click.option(
    "signature_patterns",
    "--signatures-only",
    multiple=True,
    help="Patterns of Python files (e.g., '*.py' or 'utils.py') for which to extract only function signatures and docstrings. Only works with Python files.",
)
@click.version_option()
def cli(
    paths,
    extensions,
    include_hidden,
    ignore_files_only,
    ignore_gitignore,
    ignore_patterns,
    output_file,
    claude_xml,
    markdown,
    line_numbers,
    null,
    signature_patterns,
):
    """
    Takes one or more paths to files or directories and outputs every file,
    recursively, each one preceded with its filename like this:

    \b
        path/to/file.py
        ----
        Contents of file.py goes here
        ---
        path/to/file2.py
        ---
        ...

    If the `--cxml` flag is provided, the output will be structured as follows:

    \b
        <documents>
        <document path="path/to/file1.txt">
        Contents of file1.txt
        </document>
        <document path="path/to/file2.txt">
        Contents of file2.txt
        </document>
        ...
        </documents>

    If the `--markdown` flag is provided, the output will be structured as follows:

    \b
        path/to/file1.py
        ```python
        Contents of file1.py
        ```
    """
    # Reset global_index for pytest
    global global_index
    global_index = 1

    # Read paths from stdin if available
    stdin_paths = read_paths_from_stdin(use_null_separator=null)

    # Combine paths from arguments and stdin
    paths = [*paths, *stdin_paths]

    gitignore_rules = []
    writer = click.echo
    fp = None
    if output_file:
        fp = open(output_file, "w", encoding="utf-8")
        writer = lambda s: print(s, file=fp)
    
    for path in paths:
        if not os.path.exists(path):
            raise click.BadArgumentUsage(f"Path does not exist: {path}")
        if not ignore_gitignore:
            gitignore_rules.extend(read_gitignore(os.path.dirname(path)))
        if claude_xml and path == paths[0]:
            writer("<documents>")
        process_path(
            path,
            extensions,
            include_hidden,
            ignore_files_only,
            ignore_gitignore,
            gitignore_rules,
            ignore_patterns,
            writer,
            claude_xml,
            markdown,
            line_numbers,
            signature_patterns,
        )
    if claude_xml:
        writer("</documents>")
    if fp:
        fp.close()