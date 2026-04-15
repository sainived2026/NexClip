
import os

def count_lines():
    extensions = {'.py', '.tsx', '.ts', '.js', '.json', '.sh', '.md', '.bat', '.ps1'}
    total_lines = 0
    for root, dirs, files in os.walk('.'):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                        total_lines += sum(1 for _ in f)
                except:
                    pass
    return total_lines

print(count_lines())
