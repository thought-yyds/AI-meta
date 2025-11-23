<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue';
import SessionList from './components/SessionList.vue';
import TaskChatPanel from './components/TaskChatPanel.vue';
import TaskInsightPanel from './components/TaskInsightPanel.vue';
import Auth from './components/Auth.vue';

const isAuthenticated = ref(false);
const currentSessionId = ref<number | null>(null);
const taskExecutionState = ref<any>(null);
const username = ref<string>('');

// Resizable panel widths
const leftPanelWidth = ref(280);
const rightPanelWidth = ref(320);
const savedRightPanelWidth = ref(320); // Store width when not collapsed
const isResizingLeft = ref(false);
const isResizingRight = ref(false);
const isRightPanelCollapsed = ref(false);

// Load saved widths from localStorage
onMounted(() => {
  checkAuth();
  const savedLeftWidth = localStorage.getItem('leftPanelWidth');
  const savedRightWidth = localStorage.getItem('rightPanelWidth');
  if (savedLeftWidth) {
    leftPanelWidth.value = parseInt(savedLeftWidth, 10);
  }
  if (savedRightWidth) {
    rightPanelWidth.value = parseInt(savedRightWidth, 10);
    savedRightPanelWidth.value = rightPanelWidth.value;
  }
});

// Save widths to localStorage
const saveWidths = () => {
  localStorage.setItem('leftPanelWidth', leftPanelWidth.value.toString());
  localStorage.setItem('rightPanelWidth', rightPanelWidth.value.toString());
};

// Left panel resize handlers
const startResizeLeft = (e: MouseEvent) => {
  isResizingLeft.value = true;
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
  document.addEventListener('mousemove', handleResizeLeft);
  document.addEventListener('mouseup', stopResizeLeft);
  e.preventDefault();
};

const handleResizeLeft = (e: MouseEvent) => {
  if (!isResizingLeft.value) return;
  const margin = 12; // 0.5rem * 2 = 12px
  const newWidth = e.clientX - margin;
  if (newWidth >= 200 && newWidth <= 800) {
    leftPanelWidth.value = newWidth;
  }
};

const stopResizeLeft = () => {
  isResizingLeft.value = false;
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
  document.removeEventListener('mousemove', handleResizeLeft);
  document.removeEventListener('mouseup', stopResizeLeft);
  saveWidths();
};

// Right panel resize handlers
const startResizeRight = (e: MouseEvent) => {
  isResizingRight.value = true;
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
  document.addEventListener('mousemove', handleResizeRight);
  document.addEventListener('mouseup', stopResizeRight);
  e.preventDefault();
};

const handleResizeRight = (e: MouseEvent) => {
  if (!isResizingRight.value || isRightPanelCollapsed.value) return;
  const margin = 12; // 0.5rem * 2 = 12px
  const containerWidth = window.innerWidth;
  const newWidth = containerWidth - e.clientX - margin;
  if (newWidth >= 200 && newWidth <= 800) {
    rightPanelWidth.value = newWidth;
    savedRightPanelWidth.value = newWidth;
  }
};

const stopResizeRight = () => {
  isResizingRight.value = false;
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
  document.removeEventListener('mousemove', handleResizeRight);
  document.removeEventListener('mouseup', stopResizeRight);
  saveWidths();
};

// Cleanup on unmount
onUnmounted(() => {
  document.removeEventListener('mousemove', handleResizeLeft);
  document.removeEventListener('mouseup', stopResizeLeft);
  document.removeEventListener('mousemove', handleResizeRight);
  document.removeEventListener('mouseup', stopResizeRight);
});

const checkAuth = () => {
  const token = localStorage.getItem('access_token');
  isAuthenticated.value = !!token;
  if (token) {
    // Try to decode username from token (simple base64 decode)
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      username.value = payload.sub || '用户';
    } catch {
      username.value = '用户';
    }
  }
};

const handleAuthenticated = () => {
  isAuthenticated.value = true;
  checkAuth();
};

const sessionListRef = ref<InstanceType<typeof SessionList> | null>(null);

const handleSessionCreated = (sessionId: number) => {
  currentSessionId.value = sessionId;
  // Refresh session list to show the new session
  if (sessionListRef.value) {
    sessionListRef.value.loadSessions();
  }
};

const handleSessionSelected = (sessionId: number | null) => {
  currentSessionId.value = sessionId;
};

const handleMessageSent = () => {
  // Handle message sent event
};

const handleTaskStateUpdate = (state: any) => {
  taskExecutionState.value = state;
};

const handleRightPanelCollapse = (collapsed: boolean) => {
  isRightPanelCollapsed.value = collapsed;
  if (collapsed) {
    savedRightPanelWidth.value = rightPanelWidth.value;
    rightPanelWidth.value = 60;
  } else {
    rightPanelWidth.value = savedRightPanelWidth.value;
  }
  saveWidths();
};

const handleLogout = () => {
  localStorage.removeItem('access_token');
  isAuthenticated.value = false;
  username.value = '';
  currentSessionId.value = null;
  taskExecutionState.value = null;
};
</script>

<template>
  <Auth v-if="!isAuthenticated" @authenticated="handleAuthenticated" />
  <div v-else class="app-container">
    <!-- Top Navigation Bar -->
    <nav class="top-nav">
      <div class="nav-left">
        <div class="logo">
          <span class="logo-icon">🤖</span>
          <span class="logo-text">AI Agent Assistant</span>
        </div>
      </div>
      <div class="nav-right">
        <div class="user-info">
          <span class="user-avatar">{{ username.charAt(0).toUpperCase() }}</span>
          <span class="username">{{ username }}</span>
        </div>
        <button @click="handleLogout" class="logout-btn" title="登出">
          <span class="logout-icon">🚪</span>
          <span class="logout-text">登出</span>
        </button>
      </div>
    </nav>

    <!-- Main Content - Three Column Layout -->
    <div class="main-content">
      <!-- Left Sidebar: Session List -->
      <div class="left-panel" :style="{ width: leftPanelWidth + 'px' }">
        <SessionList 
          ref="sessionListRef" 
          :selected-session-id="currentSessionId"
          @session-selected="handleSessionSelected" 
        />
      </div>

      <!-- Left Resizer -->
      <div
        class="resizer resizer-left"
        :class="{ active: isResizingLeft }"
        @mousedown="startResizeLeft"
      ></div>

      <!-- Center: Task Panel + Chat Panel -->
      <div class="center-panel">
        <TaskChatPanel
          :session-id="currentSessionId ?? undefined"
          :username="username"
          @session-created="handleSessionCreated"
          @message-sent="handleMessageSent"
          @task-state-update="handleTaskStateUpdate"
        />
      </div>

      <!-- Right Resizer -->
      <div
        class="resizer resizer-right"
        :class="{ active: isResizingRight }"
        @mousedown="startResizeRight"
      ></div>

      <!-- Right Sidebar: Task Insight Panel -->
      <div class="right-panel" :style="{ width: rightPanelWidth + 'px' }">
        <TaskInsightPanel
          :task-execution-state="taskExecutionState"
          @collapse-changed="handleRightPanelCollapse"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.top-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  z-index: 100;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.nav-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-weight: 700;
  font-size: 1.25rem;
  color: #333;
}

.logo-icon {
  font-size: 1.5rem;
}

.logo-text {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: rgba(102, 126, 234, 0.1);
  border-radius: 20px;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.9rem;
}

.username {
  font-weight: 500;
  color: #333;
  font-size: 0.95rem;
}

.logout-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: transparent;
  border: 1px solid rgba(102, 126, 234, 0.3);
  border-radius: 8px;
  color: #667eea;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s ease;
  font-size: 0.9rem;
}

.logout-btn:hover {
  background: rgba(102, 126, 234, 0.1);
  border-color: #667eea;
  transform: translateY(-1px);
}

.logout-icon {
  font-size: 1rem;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  margin: 0.5rem;
  gap: 0;
  min-height: 0;
  position: relative;
  background: transparent;
}

.left-panel {
  flex-shrink: 0;
  height: 100%;
  overflow: hidden;
  background: white;
  border-radius: 8px 0 0 8px;
}

.right-panel {
  flex-shrink: 0;
  height: 100%;
  overflow: hidden;
  background: white;
  border-radius: 0 8px 8px 0;
}

.center-panel {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow: hidden;
  background: white;
  border-radius: 0;
}

.resizer {
  width: 4px;
  background: rgba(255, 255, 255, 0.2);
  cursor: col-resize;
  flex-shrink: 0;
  position: relative;
  transition: background 0.2s ease, width 0.2s ease;
  z-index: 10;
}

.resizer:hover {
  background: rgba(102, 126, 234, 0.5);
  width: 6px;
}

.resizer.active {
  background: rgba(102, 126, 234, 0.8);
  width: 6px;
}

.resizer::before {
  content: '';
  position: absolute;
  left: -4px;
  right: -4px;
  top: 0;
  bottom: 0;
  cursor: col-resize;
}

.resizer-left {
  margin-left: 0.375rem;
  margin-right: 0.375rem;
}

.resizer-right {
  margin-left: 0.375rem;
  margin-right: 0.375rem;
}

@media (max-width: 768px) {
  .top-nav {
    padding: 0.5rem 1rem;
  }

  .logo-text {
    display: none;
  }

  .username {
    display: none;
  }

  .logout-text {
    display: none;
  }

  .main-content {
    margin: 0.25rem;
    gap: 0.25rem;
  }
}
</style>
