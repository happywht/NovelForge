import re

# Read the file
file_path = r"d:\家庭\副业探索\小说项目\NovelForge\backend\app\schemas\entity.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the UpdateDynamicInfo class and add the validator
# Pattern to match the delete_info_list field
pattern = r'(class UpdateDynamicInfo\(BaseModel\):.*?delete_info_list: Optional\[List\[DeletionInfo\]\] = Field\(default=None, description="（可选）为新增信息腾出空间而要删除的旧信息列表"\))\s*\n'

replacement = r'''\1
    
    @field_validator('delete_info_list', mode='before')
    @classmethod
    def _handle_null_string(cls, v: Any) -> Any:
        """处理 LLM 返回字符串 'null' 的情况"""
        if v is None or (isinstance(v, str) and v.lower() in ('null', 'none', '')):
            return None
        return v

'''

# Apply the replacement
new_content = re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)

# Write back
if new_content != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(" Added field validator to UpdateDynamicInfo class")
else:
    print("❌ Pattern not matched. Content unchanged.")
