import os

path = r"d:\家庭\副业探索\小说项目\NovelForge\frontend\src\renderer\src\views\Editor.vue"

with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # 修复乱码注释
    if "杞彂浜嬩欢" in line or "杩欓噷鍙槸淇濇寔浜嬩欢閾" in line:
        if "onExtractDynamicInfo" in lines[lines.index(line)-1] or "onExtractDynamicInfo" in line:
             line = line.replace(line.strip(), "// 转发事件，实际处理在CodeMirrorEditor中") if "杞彂浜嬩欢" in line else line.replace(line.strip(), "// 这里只是保持事件链")
        elif "onExtractRelations" in lines[lines.index(line)-1] or "onExtractRelations" in line:
             line = line.replace(line.strip(), "// 转发事件，实际处理在CodeMirrorEditor中") if "杞彂浜嬩欢" in line else line.replace(line.strip(), "// 这里只是保持事件链")
    
    # 修复缩进
    if "window.removeEventListener('nf:run-workflow'" in line:
        line = "    window.removeEventListener('nf:run-workflow', handleRunWorkflow as any)\n"
    
    new_lines.append(line)

# 再次检查乱码，如果上面的逻辑没中，直接按行号修复（根据之前的 view_file）
# 1269, 1270, 1325, 1326
try:
    if "杞彂" in new_lines[1268]: new_lines[1268] = "    // 转发事件，实际处理在CodeMirrorEditor中\n"
    if "淇濇寔" in new_lines[1269]: new_lines[1269] = "    // 这里只是保持事件链\n"
    if "杞彂" in new_lines[1324]: new_lines[1324] = "    // 转发事件，实际处理在CodeMirrorEditor中\n"
    if "淇濇寔" in new_lines[1325]: new_lines[1325] = "    // 这里只是保持事件链\n"
except:
    pass

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed Editor.vue encoding and indentation.")
