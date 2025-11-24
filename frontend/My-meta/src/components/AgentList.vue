<template>
  <div class="agent-list">
    <div class="agent-list-header">
      <h2>🛠️ 可用工具</h2>
    </div>

    <div class="agents">
      <div
        v-for="tool in tools"
        :key="tool.name"
        class="agent-item"
        :title="tool.description"
      >
        <div class="agent-icon">{{ tool.icon }}</div>
        <div class="agent-info">
          <div class="agent-name">{{ tool.displayName }}</div>
          <div class="agent-desc">{{ tool.description }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

export interface Tool {
  name: string;
  displayName: string;
  description: string;
  icon: string;
}

// Available tools list (matching backend Agent tools)
const tools = ref<Tool[]>([
  {
    name: 'file_parser',
    displayName: '文件解析',
    description: '解析文档（pptx, pdf, docx, txt, md）并返回结构化文本',
    icon: '📄',
  },
  {
    name: 'retrieval',
    displayName: '本地检索',
    description: '在本地文本文件中进行轻量级词法搜索，返回匹配结果',
    icon: '🔍',
  },
  {
    name: 'web_search',
    displayName: '网络搜索',
    description: '使用 Tavily API 搜索网络并返回结构化页面摘要和内容',
    icon: '🌐',
  },
  {
    name: 'github_mcp_tool',
    displayName: 'GitHub 仓库',
    description: '检查 GitHub 仓库、获取元数据或搜索代码',
    icon: '💻',
  },
  {
    name: 'send_email',
    displayName: '邮件发送',
    description: '通过配置的 SMTP 服务器发送邮件，支持附件和抄送',
    icon: '📧',
  },
  {
    name: 'add_calendar_event',
    displayName: '日历事件',
    description: '创建日历事件文件（iCal 格式），可导入到日历应用',
    icon: '📅',
  },
  {
    name: 'create_meeting',
    displayName: '创建会议',
    description: '创建新的会议。支持腾讯会议、Zoom、Microsoft Teams 等常见会议应用',
    icon: '🎬',
  },
  {
    name: 'join_meeting',
    displayName: '加入会议',
    description: '加入现有会议。支持通过会议ID、会议链接等方式加入会议',
    icon: '🚪',
  },
  {
    name: 'capture_slide_content',
    displayName: '捕获幻灯片',
    description: '专门捕获会议PPT/共享屏幕内容。使用OCR提取屏幕上的文字，并保存截图',
    icon: '📸',
  },
  {
    name: 'capture_specific_region',
    displayName: '捕获区域',
    description: '捕获屏幕特定区域（如白板、讨论区）。用于抓取重点讨论内容',
    icon: '🎯',
  },
  {
    name: 'monitor_screen_changes',
    displayName: '监控屏幕变化',
    description: '持续监控屏幕变化，检测幻灯片翻页或内容更新。当检测到变化时自动捕获',
    icon: '👁️',
  },
  {
    name: 'auto_capture_important_regions',
    displayName: '自动捕获重要区域',
    description: '自动识别并截图屏幕上的重要区域（如PPT、白板、聊天区、讨论区等）',
    icon: '🤖',
  },
  {
    name: 'extract_structured_agenda',
    displayName: '提取结构化议程',
    description: '从OCR文本中提取结构化议程。返回议程项列表，包含议程项名称、预计时间、主讲人等信息',
    icon: '📋',
  },
  {
    name: 'identify_action_items',
    displayName: '识别行动项',
    description: '识别讨论中的行动项和责任人。返回行动项列表，包含具体行动、负责人、截止时间等信息',
    icon: '✅',
  },
  {
    name: 'extract_decisions',
    displayName: '提取决策',
    description: '提取会议中的决策和结论。返回决策列表，包含决策内容、依据、影响等信息',
    icon: '💡',
  },
  {
    name: 'summarize_key_points',
    displayName: '总结要点',
    description: '总结会议核心要点。返回包含关键决策、行动项、开放问题等结构化摘要',
    icon: '📝',
  },
]);
</script>

<style scoped>
.agent-list {
  width: 100%;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.agent-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
}

.agent-list-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.agents {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
}

.agent-item {
  padding: 1rem;
  margin-bottom: 0.5rem;
  border-radius: 12px;
  position: relative;
  transition: all 0.2s ease;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.agent-item:hover {
  background: rgba(102, 126, 234, 0.05);
  border-color: rgba(102, 126, 234, 0.15);
}

.agent-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.agent-info {
  flex: 1;
  min-width: 0;
}

.agent-name {
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: #213547;
  font-size: 0.95rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-desc {
  font-size: 0.75rem;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

</style>

