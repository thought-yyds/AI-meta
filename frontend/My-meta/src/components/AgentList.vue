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
    name: 'web_search',
    displayName: '网络搜索',
    description: '使用 Tavily API 搜索网络并返回结构化页面摘要和内容',
    icon: '🌐',
  },
  {
    name: 'github_repo_info',
    displayName: 'GitHub 仓库信息',
    description: '读取仓库基本信息，如星标数、分支、描述等',
    icon: '📊',
  },
  {
    name: 'github_search_code',
    displayName: 'GitHub 代码搜索',
    description: '使用 GitHub Search API 根据关键词定位代码',
    icon: '🧭',
  },
  {
    name: 'send_mail',
    displayName: 'QQ 邮箱发送',
    description: '通过 QQ 邮箱 FastMCP 发送邮件，支持附件、定时、批量',
    icon: '📧',
  },
  {
    name: 'list_recent_mail',
    displayName: '最近邮件',
    description: '列出收件箱中的最新邮件摘要，便于快速查看',
    icon: '🗂️',
  },
  {
    name: 'read_mail',
    displayName: '读取邮件',
    description: '按 UID 读取邮件全文并可选下载附件',
    icon: '📬',
  },
  {
    name: 'add_calendar_event',
    displayName: '日历事件',
    description: '创建日历事件文件（iCal 格式），可导入到日历应用',
    icon: '📅',
  },
  {
    name: 'memory_search',
    displayName: '记忆检索',
    description: '向量 + 关键词混合策略检索最近一个月的历史对话',
    icon: '🧠',
  },
  {
    name: 'memory_refresh',
    displayName: '记忆刷新',
    description: '强制重建记忆向量索引，纳入最新对话内容',
    icon: '♻️',
  },
  {
    name: 'plan_trip',
    displayName: '行程规划',
    description: '调用高德地图，根据城市和兴趣生成包含时间段的旅行计划',
    icon: '🗺️',
  },
  {
    name: 'poi_search',
    displayName: '景点检索',
    description: '使用高德搜索指定城市/关键词的 POI 信息',
    icon: '📍',
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

