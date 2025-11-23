<template>
  <div class="task-chat-panel">
    <!-- 聊天界面 -->
    <div class="chat-section">
      <div class="chat-header">
        <h2>{{ currentSession?.title || '新对话' }}</h2>
        <div class="header-date">{{ getCurrentDate() }}</div>
      </div>

      <div class="chat-messages" ref="messagesContainer" :class="{ 'has-messages': messages.length > 0 }">
        <!-- 消息列表 -->
        <div
          v-for="message in messages"
          :key="message.id"
          :class="['message', message.role]"
        >
          <div class="message-avatar">
            {{ message.role === 'user' ? '👤' : '🤖' }}
          </div>
          <div class="message-content">
            <div class="message-text">{{ message.content }}</div>
            <div class="message-time">{{ formatTime(message.created_at) }}</div>
          </div>
        </div>
        <div v-if="isLoading" class="message assistant">
          <div class="message-avatar">🤖</div>
          <div class="message-content">
            <div class="message-text typing">思考中...</div>
          </div>
        </div>
        <!-- 错误消息 -->
        <div v-if="errorMessage" class="error-message">
          <div class="error-icon">⚠️</div>
          <div class="error-content">
            <div class="error-text">{{ errorMessage }}</div>
            <button v-if="errorRequiresAuth" @click="handleReauth" class="error-action-btn">
              重新登录
            </button>
          </div>
        </div>
      </div>

      <div class="chat-input-container" :class="{ 'centered': messages.length === 0 }">
        <!-- 欢迎消息 -->
        <div v-if="messages.length === 0" class="welcome-message">
          <div class="welcome-content">
            <div class="welcome-greeting">
              <div class="greeting-text">
                你好，{{ props.username || '用户' }}！有什么能帮到你？
              </div>
            </div>
          </div>
        </div>
        
        <div class="input-wrapper">
          <input
            type="file"
            ref="fileInput"
            @change="handleFileSelect"
            accept=".pdf,.docx,.pptx,.txt,.md,.markdown"
            style="display: none"
          />
          <button
            @click="triggerFileUpload"
            class="upload-button"
            :disabled="isLoading"
            title="上传文档 (PDF, DOCX, PPTX, TXT, MD)"
          >
            📎
          </button>
          <textarea
            v-model="inputMessage"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.shift.enter.exact="inputMessage += '\n'"
            placeholder="输入您的任务... (Enter 发送，Shift+Enter 换行)"
            class="chat-input"
            :disabled="isLoading"
            rows="1"
          ></textarea>
          <div class="input-actions">
            <button
              @click="sendMessage"
              :disabled="!inputMessage.trim() || isLoading"
              class="send-button"
            >
              {{ isLoading ? '处理中...' : '发送' }}
            </button>
          </div>
        </div>
        <!-- 上传状态提示 -->
        <div v-if="uploadStatus" class="upload-status" :class="uploadStatus.type">
          <div class="upload-status-content">
            <span>{{ uploadStatus.message }}</span>
            <div v-if="uploadStatus.type === 'uploading' && uploadStatus.progress !== undefined" class="upload-progress">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: uploadStatus.progress + '%' }"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { apiService, type Message, type ExecutionStep } from '../services/api';

const props = defineProps<{
  sessionId?: number;
  agentId?: number | null;
  username?: string;
}>();

const emit = defineEmits<{
  (e: 'session-created', sessionId: number): void;
  (e: 'message-sent'): void;
  (e: 'task-state-update', state: any): void;
}>();

// Extended Message interface with execution steps
interface MessageWithSteps extends Message {
  execution_steps?: ExecutionStep[];
}

// Chat state
const messages = ref<MessageWithSteps[]>([]);
const inputMessage = ref('');
const isLoading = ref(false);
const currentSession = ref<{ id: number; title: string } | null>(null);
const messagesContainer = ref<HTMLElement | null>(null);
const errorMessage = ref('');
const errorRequiresAuth = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const uploadStatus = ref<{ type: 'success' | 'error' | 'uploading'; message: string; progress?: number } | null>(null);

// Load messages
const loadMessages = async () => {
  if (!props.sessionId) return;
  
  try {
    messages.value = await apiService.getMessages(props.sessionId);
    // Only scroll to bottom if there are messages
    if (messages.value.length > 0) {
      scrollToBottom();
    }
  } catch (error) {
    console.error('Failed to load messages:', error);
  }
};

// Watch for session changes
watch(() => props.sessionId, (newId) => {
  if (newId) {
    loadMessages();
  } else {
    messages.value = [];
  }
}, { immediate: true });

// Send message
const sendMessage = async () => {
  if (!inputMessage.value.trim() || isLoading.value) return;

  const userMessage = inputMessage.value.trim();
  inputMessage.value = '';
  isLoading.value = true;

  // Add user message
  const tempUserMessage: MessageWithSteps = {
    id: Date.now(),
    session_id: props.sessionId || 0,
    role: 'user',
    content: userMessage,
    created_at: new Date().toISOString(),
  };
  messages.value.push(tempUserMessage);
  scrollToBottom();

  try {
    // Send to API
    const response = await apiService.sendMessage({
      session_id: props.sessionId || undefined,
      message: userMessage,
    });

    // Check if a new session was created
    if (response.session_id && response.session_id !== props.sessionId) {
      emit('session-created', response.session_id);
    }
    
    // Reload all messages to get both user and assistant messages from database
    // This ensures we have the correct user message with proper ID
    if (response.session_id) {
      messages.value = await apiService.getMessages(response.session_id);
      // Find the assistant message and add execution steps to it
      const lastMessage = messages.value[messages.value.length - 1];
      if (lastMessage && lastMessage.role === 'assistant') {
        (lastMessage as MessageWithSteps).execution_steps = response.execution_steps;
      }
    } else {
      // Fallback: if no session_id, replace temp message and add assistant message
      messages.value = messages.value.filter(m => m.id !== tempUserMessage.id);
      // Add user message (we need to create it since API doesn't return it)
      const savedUserMessage: MessageWithSteps = {
        id: Date.now() - 1, // Use a timestamp slightly before assistant message
        session_id: props.sessionId || 0,
        role: 'user',
        content: userMessage,
        created_at: new Date().toISOString(),
      };
      messages.value.push(savedUserMessage);
      
      // Add assistant message with execution steps
      const assistantMessage: MessageWithSteps = {
        ...response.message,
        execution_steps: response.execution_steps,
      };
      messages.value.push(assistantMessage);
    }
    
    // Convert execution steps to task execution state and emit to parent
    // Emit updates immediately when execution steps are available
    if (response.execution_steps && response.execution_steps.length > 0) {
      const taskState = convertExecutionStepsToTaskState(response.execution_steps);
      emit('task-state-update', taskState);
    }
    
    emit('message-sent');
    scrollToBottom();
  } catch (error: any) {
    console.error('Failed to send message:', error);
    
    // Extract user-friendly error message
    let message = '发送消息失败，请稍后重试';
    let requiresAuth = false;
    
    if (error) {
      // Check if it's an Error object with a proper message
      if (error instanceof Error) {
        const errorMsg = error.message;
        // Filter out object string representations
        if (errorMsg && !errorMsg.includes('<') && !errorMsg.includes('object at')) {
          message = errorMsg;
        }
      } else if (typeof error === 'string') {
        // If error is a string, use it directly (but filter out object strings)
        if (!error.includes('<') && !error.includes('object at')) {
          message = error;
        }
      }
      
      // Check for authentication errors
      if (error.status === 401 || error.requiresAuth) {
        requiresAuth = true;
        message = message || '登录已过期，请重新登录';
      }
    }
    
    // Display error message
    errorMessage.value = message;
    errorRequiresAuth.value = requiresAuth;
    
    // Auto-hide error message after 5 seconds
    setTimeout(() => {
      errorMessage.value = '';
      errorRequiresAuth.value = false;
    }, 5000);
    
    // Remove user message if API call failed
    messages.value = messages.value.filter(m => m.id !== tempUserMessage.id);
  } finally {
    isLoading.value = false;
  }
};

// Handle re-authentication
const handleReauth = () => {
  localStorage.removeItem('access_token');
  window.location.reload();
};

// Convert execution steps to task execution state format
const convertExecutionStepsToTaskState = (executionSteps: ExecutionStep[]): any => {
  const steps = executionSteps.map((step, index) => {
    const hasError = step.observation?.error;
    // Determine status: if observation exists and no error, it's completed
    // If no observation yet, it's running
    // If error, it's failed
    let status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
    if (hasError) {
      status = 'failed';
    } else if (step.observation) {
      // Has observation means step is completed
      status = 'completed';
    } else {
      // No observation means step is still running
      status = 'running';
    }
    
    // Extract tool name from action
    const toolName = step.action || 'unknown';
    
    // Get user-friendly description from thought
    const description = step.thought || `执行 ${toolName}`;
    
    // Format result summary
    let resultSummary = '';
    if (step.observation) {
      if (step.observation.error) {
        resultSummary = `错误: ${step.observation.error}`;
      } else if (step.observation.content) {
        const content = typeof step.observation.content === 'string' 
          ? step.observation.content 
          : JSON.stringify(step.observation.content);
        resultSummary = content.length > 100 ? content.substring(0, 100) + '...' : content;
      } else if (step.observation.result) {
        resultSummary = String(step.observation.result);
      } else if (step.observation.message) {
        resultSummary = String(step.observation.message);
      } else if (step.observation.text) {
        resultSummary = String(step.observation.text);
      }
    }
    
    return {
      id: `step-${index}`,
      name: toolName,
      status: status,
      tool: toolName,
      args: step.action_input || {},
      result: step.observation,
      error: step.observation?.error,
      timestamp: step.timestamp ? new Date(step.timestamp).getTime() : Date.now(),
      description: description,
      resultSummary: resultSummary,
    };
  });
  
  // Find the current step (first running step, or last step if all completed)
  let currentStepIndex = steps.length - 1;
  const runningStepIndex = steps.findIndex(s => s.status === 'running');
  if (runningStepIndex !== -1) {
    currentStepIndex = runningStepIndex;
  }
  
  return {
    status: steps.some(s => s.status === 'running') ? 'running' : 
            steps.some(s => s.status === 'failed') ? 'failed' : 'completed',
    steps: steps,
    currentStepIndex: currentStepIndex,
    startTime: Date.now(),
  };
};

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value && messages.value.length > 0) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
};

const formatTime = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
};

const getCurrentDate = () => {
  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth() + 1;
  const day = today.getDate();
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
  const weekday = weekdays[today.getDay()];
  return `今天是 ${year}年${month}月${day}日 ${weekday}`;
};


// 文件上传相关
const triggerFileUpload = () => {
  fileInput.value?.click();
};

const handleFileSelect = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;

  // 检查文件类型
  const allowedExtensions = ['.pdf', '.docx', '.pptx', '.txt', '.md', '.markdown'];
  const fileExt = '.' + file.name.split('.').pop()?.toLowerCase();
  if (!allowedExtensions.includes(fileExt)) {
    uploadStatus.value = {
      type: 'error',
      message: `不支持的文件类型。支持的类型: ${allowedExtensions.join(', ')}`
    };
    setTimeout(() => { uploadStatus.value = null; }, 3000);
    return;
  }

  // 检查文件大小 (200MB)
  const maxSize = 200 * 1024 * 1024;
  if (file.size > maxSize) {
    uploadStatus.value = {
      type: 'error',
      message: `文件太大。最大允许大小: ${(maxSize / (1024 * 1024)).toFixed(0)}MB`
    };
    setTimeout(() => { uploadStatus.value = null; }, 3000);
    return;
  }

  // 格式化文件大小
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  // 检查是否使用分片上传（大于50MB）
  const useChunkedUpload = file.size > 50 * 1024 * 1024;
  
  // 上传文件
  uploadStatus.value = {
    type: 'uploading',
    message: useChunkedUpload 
      ? `正在分片上传 ${file.name} (${formatFileSize(file.size)})...`
      : `正在上传 ${file.name} (${formatFileSize(file.size)})...`,
    progress: 0
  };

  try {
    const result = await apiService.uploadFile(file, (progress) => {
      if (uploadStatus.value) {
        uploadStatus.value.progress = progress;
        if (useChunkedUpload) {
          uploadStatus.value.message = `正在分片上传 ${file.name} (${formatFileSize(file.size)})... ${progress}%`;
        } else {
          uploadStatus.value.message = `正在上传 ${file.name} (${formatFileSize(file.size)})... ${progress}%`;
        }
      }
    });
    // 根据文件大小给出不同的提示
    const isLargeFile = file.size > 10 * 1024 * 1024; // 大于10MB
    let successMessage = `✅ 文件上传成功: ${result.filename}`;
    if (isLargeFile) {
      successMessage += ` (${formatFileSize(file.size)})。提示：大文档会自动分页解析，您可以说"分析前10页"来限制解析范围`;
    } else {
      successMessage += `。现在可以对Agent说"分析这个文档"或"解析 ${result.saved_filename}"`;
    }
    
    uploadStatus.value = {
      type: 'success',
      message: successMessage
    };
    
    // 自动在输入框中添加提示文本
    if (!inputMessage.value.trim()) {
      if (isLargeFile) {
        inputMessage.value = `请分析这个文档的前20页: ${result.saved_filename}`;
      } else {
        inputMessage.value = `请分析这个文档: ${result.saved_filename}`;
      }
    }
    
    setTimeout(() => { uploadStatus.value = null; }, 5000);
  } catch (error: any) {
    console.error('File upload error:', error);
    uploadStatus.value = {
      type: 'error',
      message: error.message || '文件上传失败'
    };
    setTimeout(() => { uploadStatus.value = null; }, 5000);
  } finally {
    // 重置文件输入
    if (target) {
      target.value = '';
    }
  }
};
</script>

<style scoped>
.task-chat-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  background: transparent;
  overflow: hidden;
  animation: fadeIn 0.5s ease-out;
  position: relative;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: scale(0.98);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* 背景微动画 */
.task-chat-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    135deg,
    rgba(102, 126, 234, 0.02) 0%,
    rgba(118, 75, 162, 0.02) 50%,
    rgba(102, 126, 234, 0.02) 100%
  );
  background-size: 200% 200%;
  animation: gradientShift 15s ease infinite;
  pointer-events: none;
  z-index: 0;
}

@keyframes gradientShift {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

.task-visualization {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.03) 0%, rgba(118, 75, 162, 0.03) 100%);
  padding: 1.25rem;
  position: relative;
  z-index: 1;
  animation: slideDown 0.4s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.task-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: #213547;
}

.status-badge {
  padding: 0.4rem 0.8rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.idle {
  background: rgba(158, 158, 158, 0.2);
  color: #616161;
}

.status-badge.running {
  background: rgba(102, 126, 234, 0.2);
  color: #667eea;
  animation: pulse 2s infinite, glow 2s ease-in-out infinite;
  position: relative;
}

@keyframes glow {
  0%, 100% {
    box-shadow: 0 0 5px rgba(102, 126, 234, 0.3);
  }
  50% {
    box-shadow: 0 0 15px rgba(102, 126, 234, 0.6);
  }
}

.status-badge.completed {
  background: rgba(66, 184, 131, 0.2);
  color: #42b883;
}

.status-badge.failed {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.status-badge.paused {
  background: rgba(255, 152, 0, 0.2);
  color: #ff9800;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.mermaid-container {
  min-height: 200px;
  margin: 1rem 0;
  padding: 1rem;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  overflow-x: auto;
}

.task-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 1rem;
}

.action-btn {
  padding: 0.6rem 1.25rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn.retry {
  background: linear-gradient(135deg, #42b883 0%, #35a372 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(66, 184, 131, 0.3);
}

.action-btn.skip {
  background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(255, 152, 0, 0.3);
}

.action-btn.modify {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.action-btn.continue {
  background: linear-gradient(135deg, #42b883 0%, #35a372 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(66, 184, 131, 0.3);
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.action-btn:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
  transition: transform 0.1s ease;
}

.action-btn {
  position: relative;
  overflow: hidden;
}

.action-btn::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  transform: translate(-50%, -50%);
  transition: width 0.6s, height 0.6s;
}

.action-btn:active:not(:disabled)::after {
  width: 300px;
  height: 300px;
}

.chat-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

.chat-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chat-header::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(102, 126, 234, 0.1),
    transparent
  );
  animation: shimmer 3s infinite;
}

@keyframes shimmer {
  0% {
    left: -100%;
  }
  100% {
    left: 100%;
  }
}

.chat-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: gradientText 3s ease infinite;
  position: relative;
  z-index: 1;
}

.header-date {
  font-size: 0.875rem;
  color: rgba(102, 126, 234, 0.75);
  font-weight: 500;
  letter-spacing: 0.3px;
  position: relative;
  z-index: 1;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0.5), rgba(245, 245, 245, 0.3));
  position: relative;
  scroll-behavior: smooth;
}

.chat-messages::-webkit-scrollbar {
  width: 8px;
}

.chat-messages::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 10px;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 10px;
  transition: background 0.3s;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(135deg, #7c8ff0 0%, #8a5fb8 100%);
}

.chat-messages:not(.has-messages) {
  justify-content: flex-start;
  align-items: center;
  padding-top: 4rem;
  padding-bottom: 0;
}

.welcome-message {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  width: 100%;
  padding: 0;
  margin-bottom: 1.5rem;
}

.welcome-content {
  text-align: center;
  max-width: 100%;
  width: 100%;
  animation: fadeInUp 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
  margin: 0 auto;
}

@keyframes fadeInUp {
  0% {
    opacity: 0;
    transform: translateY(30px) scale(0.95);
  }
  50% {
    transform: translateY(-5px) scale(1.02);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.welcome-greeting {
  background: transparent;
  padding: 0 0 1.5rem 0;
  position: relative;
  overflow: hidden;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.welcome-greeting::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(102, 126, 234, 0.25) 50%, 
    transparent 100%);
}

.welcome-greeting::after {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(
    circle,
    rgba(102, 126, 234, 0.03) 0%,
    transparent 70%
  );
  pointer-events: none;
}

.greeting-text {
  font-size: 1.5rem;
  color: #213547;
  font-weight: 600;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1.6;
  letter-spacing: -0.3px;
  position: relative;
  z-index: 1;
  animation: gradientText 3s ease infinite;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
}

@keyframes gradientText {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

.message {
  display: flex;
  gap: 0.75rem;
  max-width: 75%;
  animation: slideInMessage 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  position: relative;
}

@keyframes slideInMessage {
  0% {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  50% {
    transform: translateY(-5px) scale(1.02);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
  animation: slideInMessageRight 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes slideInMessageRight {
  0% {
    opacity: 0;
    transform: translateX(30px) translateY(20px) scale(0.95);
  }
  50% {
    transform: translateX(-5px) translateY(-5px) scale(1.02);
  }
  100% {
    opacity: 1;
    transform: translateX(0) translateY(0) scale(1);
  }
}

.message.assistant {
  align-self: flex-start;
  animation: slideInMessageLeft 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes slideInMessageLeft {
  0% {
    opacity: 0;
    transform: translateX(-30px) translateY(20px) scale(0.95);
  }
  50% {
    transform: translateX(5px) translateY(-5px) scale(1.02);
  }
  100% {
    opacity: 1;
    transform: translateX(0) translateY(0) scale(1);
  }
}

.message-avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transition: all 0.3s ease;
  position: relative;
  animation: avatarPop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes avatarPop {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.message-avatar:hover {
  transform: scale(1.1) rotate(5deg);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}

.error-message {
  display: flex;
  gap: 0.75rem;
  align-self: center;
  max-width: 85%;
  margin: 1rem auto;
  padding: 1rem 1.25rem;
  background: linear-gradient(135deg, #fee 0%, #fdd 100%);
  border: 1px solid #f88;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(255, 0, 0, 0.1);
  animation: slideInMessage 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.error-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.error-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.error-text {
  color: #c33;
  font-size: 0.95rem;
  line-height: 1.5;
  font-weight: 500;
}

.error-action-btn {
  align-self: flex-start;
  padding: 0.5rem 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.error-action-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.error-action-btn:active {
  transform: translateY(0);
}

.message.user .message-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  animation: avatarPop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1), breathe 3s ease-in-out infinite;
}

.message.assistant .message-avatar {
  background: linear-gradient(135deg, #42b883 0%, #35a372 100%);
  animation: avatarPop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1), breathe 3s ease-in-out infinite 0.5s;
}

@keyframes breathe {
  0%, 100% {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }
  50% {
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
  }
}

.message-content {
  background: white;
  padding: 1rem 1.25rem;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.message-content::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  transition: left 0.5s;
}

.message:hover .message-content::before {
  left: 100%;
}

.message.user .message-content {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-content {
  border-bottom-left-radius: 4px;
}

.message-text {
  margin: 0;
  word-wrap: break-word;
  white-space: pre-wrap;
  line-height: 1.6;
  font-size: 0.95rem;
}

.message.user .message-text {
  color: white;
}

.message-text.typing {
  font-style: italic;
  opacity: 0.7;
  position: relative;
}

.message-text.typing::after {
  content: '...';
  animation: dots 1.5s steps(4, end) infinite;
}

.message-text.typing::before {
  content: '';
  position: absolute;
  left: 0;
  bottom: -2px;
  width: 0;
  height: 2px;
  background: linear-gradient(90deg, #667eea, #764ba2);
  animation: typingProgress 2s ease-in-out infinite;
}

@keyframes typingProgress {
  0% {
    width: 0;
  }
  50% {
    width: 100%;
  }
  100% {
    width: 0;
  }
}

@keyframes dots {
  0%, 20% {
    content: '.';
  }
  40% {
    content: '..';
  }
  60%, 100% {
    content: '...';
  }
}

.message-time {
  font-size: 0.7rem;
  opacity: 0.6;
  margin-top: 0.5rem;
  display: block;
}

.message.user .message-time {
  color: rgba(255, 255, 255, 0.8);
}


.chat-input-container {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  background: rgba(255, 255, 255, 0.95);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(10px);
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 10;
  position: relative;
  flex-shrink: 0;
}

.chat-input-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(102, 126, 234, 0.3),
    transparent
  );
  opacity: 0;
  transition: opacity 0.3s;
}

.chat-input-container:focus-within::before {
  opacity: 1;
  animation: borderFlow 2s linear infinite;
}

@keyframes borderFlow {
  0% {
    background-position: 0% 0%;
  }
  100% {
    background-position: 200% 0%;
  }
}

.chat-input-container.centered {
  position: absolute;
  bottom: 50%;
  left: 50%;
  transform: translateX(-50%);
  max-width: 600px;
  width: calc(100% - 4rem);
  margin: 0;
  border-radius: 24px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  border: 1px solid rgba(102, 126, 234, 0.15);
  animation: floatUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
  padding: 2rem 1.5rem 1.5rem 1.5rem;
  border-top: 1px solid rgba(102, 126, 234, 0.15);
}

@keyframes floatUp {
  from {
    opacity: 0;
    transform: translateY(30px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.input-wrapper {
  display: flex;
  flex-direction: row;
  gap: 0.75rem;
  padding: 0.875rem 1.25rem;
  align-items: center;
}

.upload-button {
  padding: 0.75rem;
  background: linear-gradient(135deg, #42b883 0%, #35a372 100%);
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 1.2rem;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 8px rgba(66, 184, 131, 0.3);
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.upload-button:hover:not(:disabled) {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 4px 12px rgba(66, 184, 131, 0.4);
}

.upload-button:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
}

.upload-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.upload-status {
  padding: 0.75rem 1rem;
  margin: 0 1.25rem 0.5rem 1.25rem;
  border-radius: 8px;
  font-size: 0.875rem;
  animation: slideInUp 0.3s ease-out;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.upload-status.uploading {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
  border: 1px solid rgba(102, 126, 234, 0.2);
}

.upload-status.success {
  background: rgba(66, 184, 131, 0.1);
  color: #42b883;
  border: 1px solid rgba(66, 184, 131, 0.2);
}

.upload-status.error {
  background: rgba(244, 67, 54, 0.1);
  color: #f44336;
  border: 1px solid rgba(244, 67, 54, 0.2);
}

.upload-status-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.upload-progress {
  margin-top: 0.5rem;
}

.progress-bar {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 3px;
  transition: width 0.3s ease-out;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.chat-input-container.centered .input-wrapper {
  padding: 0;
  width: 100%;
}

.input-actions {
  display: flex;
  gap: 0.875rem;
  align-items: center;
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  padding: 0.75rem 1rem;
  border: 2px solid rgba(102, 126, 234, 0.2);
  border-radius: 16px;
  font-family: inherit;
  font-size: 0.9rem;
  resize: none;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: white;
  line-height: 1.5;
  min-height: 44px;
  max-height: 120px;
  position: relative;
  overflow-y: auto;
}

.chat-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.15), 0 4px 20px rgba(102, 126, 234, 0.1);
  background: #fafafa;
  transform: translateY(-1px);
}

.chat-input::placeholder {
  transition: opacity 0.3s;
}

.chat-input:focus::placeholder {
  opacity: 0.5;
}

.chat-input::placeholder {
  color: #999;
  opacity: 0.7;
}

.send-button {
  padding: 0.75rem 1.5rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  white-space: nowrap;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.send-button::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  transform: translate(-50%, -50%);
  transition: width 0.6s, height 0.6s;
}

.send-button:active:not(:disabled)::before {
  width: 300px;
  height: 300px;
}

.send-button::after {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.2),
    transparent
  );
  transition: left 0.5s;
}

.send-button:hover:not(:disabled)::after {
  left: 100%;
}

.interrupt-button {
  padding: 0.75rem 1.5rem;
  background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(244, 67, 54, 0.3);
  white-space: nowrap;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.interrupt-button {
  position: relative;
  overflow: hidden;
}

.interrupt-button::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  transform: translate(-50%, -50%);
  transition: width 0.6s, height 0.6s;
}

.interrupt-button:active::before {
  width: 300px;
  height: 300px;
}

.interrupt-button:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 6px 20px rgba(244, 67, 54, 0.4);
  background: linear-gradient(135deg, #f55c47 0%, #e6392f 100%);
}

.interrupt-button:active {
  transform: translateY(0) scale(0.98);
  transition: transform 0.1s ease;
}

.send-button:hover:not(:disabled) {
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
  background: linear-gradient(135deg, #7c8ff0 0%, #8a5fb8 100%);
}

.send-button:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
  transition: transform 0.1s ease;
}

.send-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
  animation: fadeIn 0.3s ease-out;
}

.modal-content {
  background: white;
  padding: 2rem;
  border-radius: 16px;
  width: 90%;
  max-width: 500px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: modalSlideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes modalSlideIn {
  from {
    opacity: 0;
    transform: translateY(-50px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.modal-content h3 {
  margin: 0 0 1.5rem 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #213547;
}

.modal-textarea {
  width: 100%;
  padding: 0.75rem;
  margin-bottom: 1rem;
  border: 2px solid rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  font-size: 0.95rem;
  font-family: 'Courier New', monospace;
  box-sizing: border-box;
}

.modal-textarea:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.modal-btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.2s ease;
}

.modal-btn.primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.modal-btn.primary:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.modal-btn.primary:active {
  transform: translateY(0) scale(0.98);
  transition: transform 0.1s ease;
}

.modal-btn:not(.primary) {
  background: rgba(0, 0, 0, 0.05);
  color: #333;
}

.modal-btn:not(.primary):hover {
  background: rgba(0, 0, 0, 0.1);
}
</style>

