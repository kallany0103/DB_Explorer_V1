import os
import re

target_dirs = ['dialogs', 'widgets']
for d in target_dirs:
    for root, dirs, files in os.walk(d):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f: 
                    content = f.read()
                
                # We specifically target the QTabWidget::pane and QTabBar::tab rules 
                # that were pasted in all these dialogs
                new_content = re.sub(r'QTabWidget::pane\s*{[^}]*}\s*', '', content)
                new_content = re.sub(r'QTabBar::tab\s*{[^}]*}\s*', '', new_content)
                new_content = re.sub(r'QTabBar::tab:selected\s*{[^}]*}\s*', '', new_content)
                new_content = re.sub(r'QTabBar::tab:hover:[^\s{]*\s*{[^}]*}\s*', '', new_content)
                new_content = re.sub(r'QTabBar::tab:hover\s*{[^}]*}\s*', '', new_content)
                
                if new_content != content:
                    with open(path, 'w', encoding='utf-8') as f: 
                        f.write(new_content)
                    print(f'Updated {path}')
