import os
import re

files_to_update = [
    'GEMINI.md',
    'ROADMAP.md',
    'article.txt',
    'dataset instructions.txt',
    'Instructions.txt'
]

replacements = [
    (r'(?i)19th-century', 'Medieval'),
    (r'(?i)nineteenth-century', 'Medieval'),
    (r'(?i)nineteenth century', 'Medieval'),
    (r'1750[–-]1920', '500–1500'),
    (r'1820\s+and\s+1900', '500 and 1500'),
    (r'1900-1933', '1300-1400'),
    (r'(?i)Wagnerism', 'Gregorian Chant'),
    (r'(?i)industrial-era', 'feudal-era')
]

for filepath in files_to_update:
    if not os.path.exists(filepath):
        continue
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old_pat, new_str in replacements:
        new_content = re.sub(old_pat, new_str, new_content)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Updated {filepath}")
