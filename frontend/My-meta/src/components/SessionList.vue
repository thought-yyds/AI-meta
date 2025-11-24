<template>
  <div class="session-list">
    <div class="session-list-header">
      <h2>聊天会话</h2>
      <button @click="createNewSession" class="new-session-btn">+ 新建</button>
    </div>
    
    <div class="sessions" ref="sessionsRef" :style="{ flexBasis: sessionsHeight + 'px' }">
      <div
        v-for="session in sessions"
        :key="session.id"
        :class="['session-item', { active: session.id === selectedSessionId }]"
        @click="selectSession(session.id)"
      >
        <div class="session-title">{{ session.title }}</div>
        <div class="session-meta">
          <span>{{ session.message_count }} 条消息</span>
          <span>{{ formatDate(session.updated_at || session.created_at) }}</span>
        </div>
        <button
          @click.stop="deleteSession(session.id)"
          class="delete-btn"
          title="删除会话"
        >
          ×
        </button>
      </div>
      
      <div v-if="sessions.length === 0" class="empty-state">
        <p>还没有会话。创建一个新会话来开始吧！</p>
      </div>
    </div>

    <!-- 可调整大小的分隔条 -->
    <div 
      class="resizer" 
      ref="resizerRef"
      @mousedown="startResize"
      @touchstart="startResize"
    >
      <div class="resizer-handle"></div>
    </div>

    <!-- 可用工具栏 -->
    <div class="reminder-section" ref="reminderRef" :style="{ flexBasis: reminderHeight + 'px' }">
      <div class="reminder-header">
        <h2>🛠️ 可用工具</h2>
      </div>
      <div class="reminder-content tools-content">
        <div
          v-for="tool in tools"
          :key="tool.name"
          class="tool-item"
          :title="tool.description"
        >
          <div class="tool-icon">{{ tool.icon }}</div>
          <div class="tool-info">
            <div class="tool-name">{{ tool.displayName }}</div>
            <div class="tool-desc">{{ tool.description }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue';
import { apiService, type Session } from '../services/api';

// 工具列表定义
interface Tool {
  name: string;
  displayName: string;
  description: string;
  icon: string;
}

const tools: Tool[] = [
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
];

const props = defineProps<{
  selectedSessionId?: number | null;
}>();

const emit = defineEmits<{
  (e: 'session-selected', sessionId: number | null): void;
}>();

const sessions = ref<Session[]>([]);
const selectedSessionId = ref<number | null>(null);

// 可调整大小的相关状态
const sessionsRef = ref<HTMLElement | null>(null);
const reminderRef = ref<HTMLElement | null>(null);
const resizerRef = ref<HTMLElement | null>(null);
const sessionsHeight = ref(0); // 初始为0，等待初始化
const reminderHeight = ref(0); // 初始为0，等待初始化
const isResizing = ref(false);
const isInitialized = ref(false);
const startY = ref(0);
const startSessionsHeight = ref(0);
const startReminderHeight = ref(0);

// Watch for external session ID changes
watch(() => props.selectedSessionId, (newId) => {
  selectedSessionId.value = newId ?? null;
}, { immediate: true });

const loadSessions = async () => {
  try {
    sessions.value = await apiService.getSessions();
  } catch (error) {
    console.error('Failed to load sessions:', error);
  }
};

const selectSession = (sessionId: number) => {
  selectedSessionId.value = sessionId;
  emit('session-selected', sessionId);
};

const createNewSession = () => {
  selectedSessionId.value = null;
  emit('session-selected', null);
};

const deleteSession = async (sessionId: number) => {
  if (!confirm('确定要删除这个会话吗？')) {
    return;
  }

  try {
    await apiService.deleteSession(sessionId);
    if (selectedSessionId.value === sessionId) {
      selectedSessionId.value = null;
      emit('session-selected', null);
    }
    await loadSessions();
  } catch (error) {
    console.error('Failed to delete session:', error);
    alert('删除会话失败，请重试。');
  }
};

const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  
  if (days === 0) {
    return '今天';
  } else if (days === 1) {
    return '昨天';
  } else if (days < 7) {
    return `${days} 天前`;
  } else {
    return date.toLocaleDateString('zh-CN');
  }
};

// 开始调整大小
const startResize = (e: MouseEvent | TouchEvent) => {
  e.preventDefault();
  isResizing.value = true;
  const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
  startY.value = clientY;
  startSessionsHeight.value = sessionsHeight.value;
  startReminderHeight.value = reminderHeight.value;
  
  document.addEventListener('mousemove', handleResize);
  document.addEventListener('mouseup', stopResize);
  document.addEventListener('touchmove', handleResize);
  document.addEventListener('touchend', stopResize);
};

// 处理调整大小
const handleResize = (e: MouseEvent | TouchEvent) => {
  if (!isResizing.value) return;
  
  const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
  const deltaY = clientY - startY.value;
  
  const container = sessionsRef.value?.parentElement;
  if (!container) return;
  
  const containerHeight = container.clientHeight;
  const headerHeight = container.querySelector('.session-list-header')?.clientHeight || 0;
  const resizerHeight = resizerRef.value?.clientHeight || 0;
  const availableHeight = containerHeight - headerHeight - resizerHeight;
  
  // 计算新高度
  let newSessionsHeight = startSessionsHeight.value + deltaY;
  let newReminderHeight = startReminderHeight.value - deltaY;
  
  // 限制最小高度
  const minHeight = 100;
  if (newSessionsHeight < minHeight) {
    newSessionsHeight = minHeight;
    newReminderHeight = availableHeight - minHeight;
  }
  if (newReminderHeight < minHeight) {
    newReminderHeight = minHeight;
    newSessionsHeight = availableHeight - minHeight;
  }
  
  // 限制最大高度
  const maxSessionsHeight = availableHeight - minHeight;
  if (newSessionsHeight > maxSessionsHeight) {
    newSessionsHeight = maxSessionsHeight;
    newReminderHeight = minHeight;
  }
  
  sessionsHeight.value = newSessionsHeight;
  reminderHeight.value = newReminderHeight;
};

// 停止调整大小
const stopResize = () => {
  isResizing.value = false;
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
  document.removeEventListener('touchmove', handleResize);
  document.removeEventListener('touchend', stopResize);
};

// 初始化高度
const initHeights = () => {
  const container = sessionsRef.value?.parentElement;
  if (!container) return;
  
  const containerHeight = container.clientHeight;
  const headerHeight = container.querySelector('.session-list-header')?.clientHeight || 0;
  const resizerHeight = resizerRef.value?.clientHeight || 0;
  const availableHeight = containerHeight - headerHeight - resizerHeight;
  
  // 如果高度未初始化，使用默认比例
  if (!isInitialized.value && availableHeight > 0) {
    sessionsHeight.value = availableHeight * 0.6;
    reminderHeight.value = availableHeight * 0.4;
    isInitialized.value = true;
  } else if (isInitialized.value && availableHeight > 0) {
    // 如果已经初始化，保持比例但调整总高度
    const totalHeight = sessionsHeight.value + reminderHeight.value;
    if (totalHeight > 0) {
      const ratio = sessionsHeight.value / totalHeight;
      sessionsHeight.value = availableHeight * ratio;
      reminderHeight.value = availableHeight * (1 - ratio);
    }
  }
};

defineExpose({
  loadSessions,
});

onMounted(() => {
  loadSessions();
  // 延迟初始化高度，确保DOM已渲染
  setTimeout(initHeights, 100);
  // 监听窗口大小变化
  window.addEventListener('resize', initHeights);
});

onUnmounted(() => {
  stopResize();
  window.removeEventListener('resize', initHeights);
});
</script>

<style scoped>
.session-list {
  width: 100%;
  height: 100%;
  background: transparent;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.session-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
}

.session-list-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.new-session-btn {
  padding: 0.5rem 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.new-session-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.new-session-btn:active {
  transform: translateY(0);
}

.sessions {
  flex: 0 0 auto;
  overflow-y: auto;
  padding: 0.5rem;
  min-height: 100px;
}

.session-item {
  padding: 1rem;
  margin-bottom: 0.5rem;
  border-radius: 12px;
  cursor: pointer;
  position: relative;
  transition: all 0.2s ease;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.session-item:hover {
  background: rgba(102, 126, 234, 0.08);
  transform: translateX(4px);
  border-color: rgba(102, 126, 234, 0.2);
}

.session-item.active {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
  border-left: 4px solid #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
}

.session-title {
  font-weight: 600;
  margin-bottom: 0.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #213547;
  font-size: 0.95rem;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #666;
  gap: 0.5rem;
}

.session-meta span {
  padding: 0.25rem 0.5rem;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 6px;
  font-size: 0.7rem;
}

.delete-btn {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  width: 28px;
  height: 28px;
  border: none;
  background: rgba(244, 67, 54, 0.1);
  color: #f44336;
  font-size: 1.2rem;
  line-height: 1;
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s ease;
  font-weight: 300;
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: rgba(244, 67, 54, 0.2);
  transform: scale(1.1);
}

.empty-state {
  padding: 3rem 2rem;
  text-align: center;
  color: #999;
}

.empty-state p {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
}

.empty-state::before {
  content: '💭';
  display: block;
  font-size: 3rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.resizer {
  flex-shrink: 0;
  height: 8px;
  cursor: row-resize;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  transition: background 0.2s ease;
}

.resizer:hover {
  background: rgba(102, 126, 234, 0.1);
}

.resizer-handle {
  width: 40px;
  height: 4px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 2px;
  transition: background 0.2s ease;
}

.resizer:hover .resizer-handle {
  background: rgba(102, 126, 234, 0.4);
}

.resizer:active {
  background: rgba(102, 126, 234, 0.15);
}

.resizer:active .resizer-handle {
  background: rgba(102, 126, 234, 0.6);
}

.reminder-section {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.4);
  min-height: 100px;
  overflow: hidden;
}

.reminder-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
}

.reminder-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.reminder-content {
  flex: 1;
  padding: 1.5rem;
  overflow-y: auto;
  min-height: 0;
}

.reminder-placeholder {
  margin: 0;
  color: #999;
  font-size: 0.9rem;
  text-align: center;
  padding: 2rem 0;
  line-height: 1.6;
}

.tools-content {
  padding: 0.5rem;
}

.tool-item {
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  border-radius: 10px;
  position: relative;
  transition: all 0.2s ease;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  cursor: default;
}

.tool-item:hover {
  background: rgba(102, 126, 234, 0.08);
  border-color: rgba(102, 126, 234, 0.15);
  transform: translateX(2px);
}

.tool-icon {
  font-size: 1.25rem;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.tool-info {
  flex: 1;
  min-width: 0;
}

.tool-name {
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: #213547;
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-desc {
  font-size: 0.7rem;
  color: #666;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@media (max-width: 768px) {
  .session-list {
    width: 280px;
  }

  .session-list-header {
    padding: 1rem;
  }

  .session-list-header h2 {
    font-size: 1.1rem;
  }
}
</style>

