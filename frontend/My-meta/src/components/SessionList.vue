<template>
  <div class="session-list">
    <div class="session-list-header">
      <h2>聊天会话</h2>
      <button @click="createNewSession" class="new-session-btn">+ 新建</button>
    </div>
    
    <div class="sessions">
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { apiService, type Session } from '../services/api';

const props = defineProps<{
  selectedSessionId?: number | null;
}>();

const emit = defineEmits<{
  (e: 'session-selected', sessionId: number | null): void;
}>();

const sessions = ref<Session[]>([]);
const selectedSessionId = ref<number | null>(null);

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

defineExpose({
  loadSessions,
});

onMounted(() => {
  loadSessions();
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
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
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

