import os

file_path = r'd:\家庭\副业探索\小说项目\NovelForge\frontend\src\renderer\src\views\Editor.vue'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 1. Fix event listeners in onMounted
on_mounted_start = -1
for i, line in enumerate(lines):
    if 'onMounted(async () => {' in line:
        on_mounted_start = i
        break

if on_mounted_start != -1:
    # Check if already exists
    exists = any("'nf:run-workflow'" in line for line in lines[on_mounted_start:on_mounted_start+20])
    if not exists:
        # Find the end of onMounted
        on_mounted_end = -1
        for i in range(on_mounted_start, len(lines)):
            if '})' in lines[i] and (i == len(lines)-1 or 'onBeforeUnmount' in lines[i+1] or 'function' in lines[i+1]):
                on_mounted_end = i
                break
        
        if on_mounted_end != -1:
            lines.insert(on_mounted_end, "  window.addEventListener('nf:run-workflow', handleRunWorkflow as any)\n")

# 2. Fix cleanup in onBeforeUnmount (indentation)
for i, line in enumerate(lines):
    if "window.removeEventListener('nf:run-workflow', handleRunWorkflow as any)" in line:
        lines[i] = "    window.removeEventListener('nf:run-workflow', handleRunWorkflow as any)\n"

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Successfully fixed event listeners in Editor.vue")
