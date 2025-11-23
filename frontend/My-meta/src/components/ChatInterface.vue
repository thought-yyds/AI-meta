<template>
  <div class="chat-container">
    <div class="chat-header">
      <h2>{{ currentSession?.title || 'New Chat' }}</h2>
      <button v-if="currentSession" @click="showSummary = !showSummary" class="summary-btn">
        {{ showSummary ? 'Hide' : 'Show' }} Summary
      </button>
    </div>

    <div class="chat-messages" ref="messagesContainer">
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
          <div class="message-text typing">Thinking...</div>
        </div>
      </div>
    </div>

    <div v-if="showSummary && summaries.length > 0" class="summary-panel">
      <h3>Conversation Summary</h3>
      <div
        v-for="summary in summaries"
        :key="summary.id"
        class="summary-item"
      >
        <p>{{ summary.content }}</p>
        <small>{{ summary.message_count }} messages • {{ formatTime(summary.created_at) }}</small>
      </div>
      <button @click="generateNewSummary" :disabled="isGeneratingSummary" class="generate-summary-btn">
        {{ isGeneratingSummary ? 'Generating...' : 'Generate New Summary' }}
      </button>
    </div>

    <div class="chat-input-container">
      <textarea
        v-model="inputMessage"
        @keydown.enter.exact.prevent="sendMessage"
        @keydown.shift.enter.exact="inputMessage += '\n'"
        placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
        class="chat-input"
        :disabled="isLoading"
        rows="3"
      ></textarea>
      <button
        @click="sendMessage"
        :disabled="!inputMessage.trim() || isLoading"
        class="send-button"
      >
        Send
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue';
import { apiService, type Message, type Summary } from '../services/api';

const props = defineProps<{
  sessionId?: number;
}>();

const emit = defineEmits<{
  (e: 'session-created', sessionId: number): void;
  (e: 'message-sent'): void;
}>();

const messages = ref<Message[]>([]);
const summaries = ref<Summary[]>([]);
const inputMessage = ref('');
const isLoading = ref(false);
const isGeneratingSummary = ref(false);
const showSummary = ref(false);
const currentSession = ref<{ id: number; title: string } | null>(null);
const messagesContainer = ref<HTMLElement | null>(null);

const loadMessages = async () => {
  if (!props.sessionId) return;
  
  try {
    messages.value = await apiService.getMessages(props.sessionId);
    await loadSummaries();
    scrollToBottom();
  } catch (error) {
    console.error('Failed to load messages:', error);
  }
};

const loadSummaries = async () => {
  if (!props.sessionId) return;
  
  try {
    summaries.value = await apiService.getSummaries(props.sessionId);
  } catch (error) {
    console.error('Failed to load summaries:', error);
  }
};

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isLoading.value) return;

  const messageText = inputMessage.value.trim();
  inputMessage.value = '';
  isLoading.value = true;

  try {
    const response = await apiService.sendMessage({
      session_id: props.sessionId,
      message: messageText,
    });

    // Update current session if it was created
    if (response.session_id && !props.sessionId) {
      currentSession.value = { id: response.session_id, title: 'New Chat' };
      emit('session-created', response.session_id);
    }

    // Reload messages to get the full conversation
    await loadMessages();

    // If summary was generated, show it
    if (response.summary) {
      summaries.value.unshift(response.summary);
      showSummary.value = true;
    }

    emit('message-sent');
  } catch (error) {
    console.error('Failed to send message:', error);
    alert('Failed to send message. Please try again.');
  } finally {
    isLoading.value = false;
  }
};

const generateNewSummary = async () => {
  if (!props.sessionId || isGeneratingSummary.value) return;

  isGeneratingSummary.value = true;
  try {
    const summary = await apiService.generateSummary(props.sessionId);
    summaries.value.unshift(summary);
    showSummary.value = true;
  } catch (error) {
    console.error('Failed to generate summary:', error);
    alert('Failed to generate summary. Please try again.');
  } finally {
    isGeneratingSummary.value = false;
  }
};

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

const formatTime = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
};

watch(() => props.sessionId, async (newId) => {
  if (newId) {
    try {
      currentSession.value = await apiService.getSession(newId);
    } catch (error) {
      console.error('Failed to load session:', error);
    }
    await loadMessages();
  } else {
    messages.value = [];
    summaries.value = [];
    currentSession.value = null;
  }
}, { immediate: true });

watch(messages, () => {
  scrollToBottom();
}, { deep: true });

onMounted(() => {
  if (props.sessionId) {
    loadMessages();
  }
});
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.chat-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.summary-btn {
  padding: 0.5rem 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.summary-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0.5), rgba(245, 245, 245, 0.3));
}

.message {
  display: flex;
  gap: 0.75rem;
  max-width: 75%;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant {
  align-self: flex-start;
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
}

.message.user .message-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.message.assistant .message-avatar {
  background: linear-gradient(135deg, #42b883 0%, #35a372 100%);
}

.message-content {
  background: white;
  padding: 1rem 1.25rem;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  position: relative;
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
}

.message-text.typing::after {
  content: '...';
  animation: dots 1.5s steps(4, end) infinite;
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

.summary-panel {
  background: rgba(255, 255, 255, 0.95);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  padding: 1.25rem;
  max-height: 250px;
  overflow-y: auto;
  backdrop-filter: blur(10px);
}

.summary-panel h3 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  font-weight: 700;
  color: #213547;
}

.summary-item {
  padding: 0.75rem;
  margin-bottom: 0.75rem;
  border-radius: 8px;
  background: rgba(102, 126, 234, 0.05);
  border-left: 3px solid #667eea;
}

.summary-item:last-child {
  margin-bottom: 0;
}

.summary-item p {
  margin: 0 0 0.5rem 0;
  font-size: 0.9rem;
  line-height: 1.5;
  color: #213547;
}

.summary-item small {
  color: #666;
  font-size: 0.75rem;
}

.generate-summary-btn {
  margin-top: 0.75rem;
  padding: 0.6rem 1.25rem;
  background: linear-gradient(135deg, #42b883 0%, #35a372 100%);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(66, 184, 131, 0.3);
  width: 100%;
}

.generate-summary-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(66, 184, 131, 0.4);
}

.generate-summary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.chat-input-container {
  display: flex;
  gap: 0.75rem;
  padding: 1.25rem 1.5rem;
  background: rgba(255, 255, 255, 0.95);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(10px);
}

.chat-input {
  flex: 1;
  padding: 0.875rem 1rem;
  border: 2px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  font-family: inherit;
  font-size: 0.95rem;
  resize: none;
  transition: all 0.2s ease;
  background: white;
  line-height: 1.5;
}

.chat-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.chat-input::placeholder {
  color: #999;
}

.send-button {
  padding: 0.875rem 2rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
  white-space: nowrap;
}

.send-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.send-button:active:not(:disabled) {
  transform: translateY(0);
}

.send-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

@media (max-width: 768px) {
  .message {
    max-width: 85%;
  }

  .chat-header {
    padding: 1rem;
  }

  .chat-messages {
    padding: 1rem;
    gap: 1rem;
  }

  .chat-input-container {
    padding: 1rem;
  }

  .send-button {
    padding: 0.875rem 1.5rem;
  }
}
</style>

