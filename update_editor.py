
import os

file_path = r'd:\家庭\副业探索\小说项目\NovelForge\frontend\src\renderer\src\views\Editor.vue'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 1. Add HistoryPanel import
import_added = False
for i, line in enumerate(lines):
    if "import OutlinePanel from '@renderer/components/panels/OutlinePanel.vue'" in line:
        lines.insert(i + 1, "import HistoryPanel from '@renderer/components/panels/HistoryPanel.vue'\n")
        import_added = True
        break

if not import_added:
    print("Warning: Could not find OutlinePanel import to insert HistoryPanel import after.")

# 2. Add handleHistoryRestored method
# We'll look for a good place to insert it, e.g., after handleEditCard or similar
method_added = False
method_code = """
async function handleHistoryRestored(content: string) {
  if (activeCard.value) {
    cardStore.updateCardContentLocally(activeCard.value.id, content)
    ElMessage.success('已恢复历史版本内容')
  }
}
"""
for i, line in enumerate(lines):
    if "async function handleEditCard" in line:
        # Find the end of this function or just insert before it
        lines.insert(i, method_code + "\n")
        method_added = True
        break

if not method_added:
    # Fallback: insert before </script>
    for i, line in enumerate(lines):
        if "</script>" in line:
            lines.insert(i, method_code + "\n")
            method_added = True
            break

# 3. Add "历史" tab pane
tab_added = False
tab_code = """
          <el-tab-pane label="历史" name="history">
            <HistoryPanel :card-id="activeCard?.id" @restored="handleHistoryRestored" />
          </el-tab-pane>
"""
for i, line in enumerate(lines):
    if '<el-tab-pane label="大纲" name="outline">' in line:
        # Find the end of this tab pane
        j = i
        while j < len(lines) and "</el-tab-pane>" not in lines[j]:
            j += 1
        lines.insert(j + 1, tab_code)
        tab_added = True
        break

if not tab_added:
    print("Warning: Could not find Outline tab to insert History tab after.")

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Successfully updated Editor.vue")
