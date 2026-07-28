#!/usr/bin/env python3
import os
import re
import sys
import webbrowser

def resolve_import(current_file, import_path):
    """Resolves relative and aliased imports to a workspace path."""
    if import_path.startswith('.'):
        dir_name = os.path.dirname(current_file)
        target = os.path.normpath(os.path.join(dir_name, import_path))
    elif import_path.startswith('@/') or import_path.startswith('~/'):
        stripped = import_path[2:]
        target_src = os.path.normpath(os.path.join('src', stripped))
        target_root = os.path.normpath(stripped)
        if os.path.exists(target_src) or any(os.path.exists(target_src + ext) for ext in ['.ts', '.tsx', '.js', '.jsx']):
            target = target_src
        else:
            target = target_root
    else:
        parts = import_path.split('/')
        if parts and os.path.isdir(parts[0]):
            target = os.path.normpath(import_path)
        else:
            return None

    if os.path.isfile(target):
        return target
        
    for ext in ['.ts', '.tsx', '.js', '.jsx']:
        if os.path.isfile(target + ext):
            return target + ext
        if os.path.isdir(target) and os.path.isfile(os.path.join(target, 'index' + ext)):
            return os.path.join(target, 'index' + ext)
            
    return target

def get_node_id(filepath):
    """Converts a filepath into a safe Mermaid node ID."""
    return filepath.replace('/', '_').replace('.', '_').replace('-', '_')

def get_node_label(filepath):
    """Gets the base filename without extension as the node label."""
    return os.path.basename(filepath)

def scan_project(scan_dirs):
    """Scans project directories for files and parses imports."""
    exclude_dirs = {'.git', '.claude', '.agents', '.next', 'node_modules', 'dist', 'build', '.shadowing', 'out', 'docs'}
    extensions = {'.ts', '.tsx', '.js', '.jsx'}
    
    file_map = {}  # filepath -> list of imports
    all_files = []
    
    for scan_dir in scan_dirs:
        if not os.path.exists(scan_dir):
            continue
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in extensions:
                    rel_path = os.path.normpath(os.path.join(root, file))
                    all_files.append(rel_path)
                    file_map[rel_path] = []

    # Import regexes
    import_regex = re.compile(r'import\s+(?:type\s+)?(?:[\w*\s{},]*\s+from\s+)?[\'"]([^\'"]+)[\'"]')
    require_regex = re.compile(r'(?:require|import)\([\'"]([^\'"]+)[\'"]\)')

    for filepath in all_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            imports = []
            for match in import_regex.finditer(content):
                imports.append(match.group(1))
            for match in require_regex.finditer(content):
                imports.append(match.group(1))
                
            resolved_imports = []
            for imp in imports:
                resolved = resolve_import(filepath, imp)
                if resolved and resolved in file_map and resolved != filepath:
                    resolved_imports.append(resolved)
            file_map[filepath] = list(set(resolved_imports))
        except Exception as e:
            print(f"Warning: Failed to read {filepath}: {e}", file=sys.stderr)
            
    return file_map

def generate_mermaid(file_map):
    """Generates Mermaid TD syntax with subgraphs based on directories."""
    # Group files by parent directory
    groups = {}
    for filepath in file_map.keys():
        dir_name = os.path.dirname(filepath)
        if not dir_name or dir_name == '.':
            dir_name = 'root'
        if dir_name not in groups:
            groups[dir_name] = []
        groups[dir_name].append(filepath)
        
    lines = []
    lines.append("graph TD")
    
    # Generate subgraphs
    for dir_path, files in groups.items():
        subgraph_id = get_node_id(dir_path)
        lines.append(f"    subgraph {subgraph_id} [\"{dir_path}\"]")
        for file in files:
            node_id = get_node_id(file)
            node_label = get_node_label(file)
            lines.append(f"        {node_id}[\"{node_label}\"]")
        lines.append("    end")
        
    # Generate edges
    edges = set()
    for filepath, imports in file_map.items():
        node_id_a = get_node_id(filepath)
        for imp in imports:
            node_id_b = get_node_id(imp)
            edge = (node_id_a, node_id_b)
            if edge not in edges:
                edges.add(edge)
                lines.append(f"    {node_id_a} --> {node_id_b}")
                
    return "\n".join(lines)

def write_html(mermaid_code, output_path):
    """Writes the HTML document with dark theme and Mermaid JS inclusion."""
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Architecture Diagram</title>
    <style>
        body {
            background-color: #1a1a1a;
            color: #e0e0e0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }
        h1 {
            color: #cc785c;
            margin-bottom: 20px;
            font-weight: 300;
        }
        #diagram-container {
            background-color: #242424;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            width: 95%;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            overflow: auto;
            display: flex;
            justify-content: center;
        }
        .mermaid {
            width: 100%;
        }
    </style>
</head>
<body>
    <h1>Project Architecture Diagram</h1>
    <div id="diagram-container">
        <pre class="mermaid">
[MERMAID_CODE]
        </pre>
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({
            startOnLoad: true,
            theme: 'dark',
            securityLevel: 'loose',
            themeVariables: {
                background: '#242424',
                primaryColor: '#cc785c',
                primaryTextColor: '#e0e0e0',
                lineColor: '#cc785c'
            }
        });
    </script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    content = html_template.replace("[MERMAID_CODE]", mermaid_code)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    scan_dirs = ['src', 'components', 'app', 'lib']
    existing_dirs = [d for d in scan_dirs if os.path.exists(d)]
    if not existing_dirs:
        # Fallback to current folder if none of the standard folders exist
        existing_dirs = ['.']
        
    print(f"Scanning directories: {existing_dirs}")
    file_map = scan_project(existing_dirs)
    
    if not file_map:
        print("No source files found to diagram.")
        return
        
    mermaid_code = generate_mermaid(file_map)
    output_path = 'docs/architecture/index.html'
    write_html(mermaid_code, output_path)
    
    print(f"HTML diagram generated successfully at {output_path}")
    
    # Try opening the file in default browser
    abs_path = os.path.abspath(output_path)
    print(f"Opening browser at file://{abs_path}")
    webbrowser.open(f"file://{abs_path}")
    print("아키텍처 다이어그램이 브라우저에서 열렸습니다.")

if __name__ == '__main__':
    main()
