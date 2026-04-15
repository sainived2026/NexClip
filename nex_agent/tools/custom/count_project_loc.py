import os

def count_lines_of_code():
    total_lines = 0
    # Files to ignore
    ignore_dirs = {'.agent', '.git', 'node_modules', '.trash', 'storage'}
    extensions = {'.py', '.tsx', '.ts', '.js', '.jsx', '.sh', '.bat', '.ps1'}
    
    for root, dirs, files in os.walk('.'):
        # Filter out directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        total_lines += sum(1 for _ in f)
                except Exception:
                    continue
    return total_lines

print(f"Total lines of code: {count_lines_of_code()}")