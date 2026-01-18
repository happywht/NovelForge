<script setup lang="ts">
import { useTheme } from '@renderer/composables/useTheme'
import { useFontSettings, DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE } from '@renderer/composables/useFontSettings'

const { isDark, toggleTheme } = useTheme()
const { fontFamily, fontSize } = useFontSettings()

const fontFamilies = [
  { label: '默认系统字体', value: DEFAULT_FONT_FAMILY },
  { label: '微软雅黑', value: '"Microsoft YaHei", sans-serif' },
  { label: '宋体', value: 'SimSun, serif' },
  { label: '黑体', value: 'SimHei, sans-serif' },
  { label: '楷体', value: 'KaiTi, serif' },
  { label: 'Arial', value: 'Arial, sans-serif' },
  { label: 'Times New Roman', value: '"Times New Roman", serif' }
]

const fontSizes = [
  { label: '小 (12px)', value: '12px' },
  { label: '标准 (14px)', value: '14px' },
  { label: '中 (16px)', value: '16px' },
  { label: '大 (18px)', value: '18px' },
  { label: '特大 (20px)', value: '20px' }
]
</script>

<template>
  <div class="appearance-settings">
    <h3>外观设置</h3>
    
    <el-form label-position="top">
      <el-form-item label="主题模式">
        <div class="theme-toggle">
          <span>{{ isDark ? '深色模式' : '浅色模式' }}</span>
          <el-switch
            v-model="isDark"
            inline-prompt
            active-text="暗"
            inactive-text="亮"
            @change="toggleTheme"
          />
        </div>
      </el-form-item>

      <el-divider />

      <el-form-item label="全局字体">
        <el-select v-model="fontFamily" placeholder="选择字体" style="width: 100%">
          <el-option
            v-for="font in fontFamilies"
            :key="font.value"
            :label="font.label"
            :value="font.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="字体大小">
        <el-select v-model="fontSize" placeholder="选择大小" style="width: 100%">
          <el-option
            v-for="size in fontSizes"
            :key="size.value"
            :label="size.label"
            :value="size.value"
          />
        </el-select>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.appearance-settings {
  padding: 20px;
  max-width: 600px;
}

.theme-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
