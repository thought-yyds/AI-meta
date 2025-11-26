<template>
  <div :class="['task-insight-panel', { collapsed: isCollapsed }]">
    <div class="panel-header">
      <h2>📊 任务洞察</h2>
      <div class="header-actions">
        <button @click="toggleCollapse" class="collapse-btn" :title="isCollapsed ? '展开' : '折叠'">
          {{ isCollapsed ? '▶' : '◀' }}
        </button>
      </div>
    </div>

    <div v-if="!isCollapsed" class="panel-content">
      <!-- Mode Toggle -->
      <div class="mode-toggle-section">
        <div class="mode-toggle">
          <button
            @click="viewMode = 'user'"
            :class="['mode-btn', { active: viewMode === 'user' }]"
            title="用户模式"
          >
            👤 用户
          </button>
          <button
            @click="viewMode = 'developer'"
            :class="['mode-btn', { active: viewMode === 'developer' }]"
            title="开发者模式"
          >
            🔧 开发
          </button>
        </div>
      </div>

      <!-- Task Overview -->
      <div class="insight-section">
        <h3>任务概览</h3>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-value">{{ taskStats.totalSteps }}</div>
            <div class="stat-label">总步骤数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ taskStats.completedSteps }}</div>
            <div class="stat-label">已完成</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ taskStats.failedSteps }}</div>
            <div class="stat-label">失败</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ formatDuration(taskStats.elapsedTime) }}</div>
            <div class="stat-label">已用时间</div>
          </div>
        </div>
      </div>

      <!-- Current Step Details -->
      <div v-if="currentStep" class="insight-section">
        <h3>当前步骤</h3>
        <div class="step-details">
          <!-- User Mode Display -->
          <template v-if="viewMode === 'user'">
            <div class="step-name">{{ getToolDisplayName(currentStep.name) }}</div>
            <div :class="['step-status', currentStep.status]">
              {{ getStatusLabel(currentStep.status) }}
            </div>
            <div v-if="currentStep.description" class="step-description">
              <strong>正在执行：</strong>
              <p>{{ currentStep.description }}</p>
            </div>
            <div v-if="currentStep.resultSummary" class="step-result-summary">
              <strong>结果总结：</strong>
              <p>{{ currentStep.resultSummary }}</p>
            </div>
            <div v-else-if="currentStep.result" class="step-result-summary">
              <strong>结果总结：</strong>
              <p>{{ formatResultSummary(currentStep.result) }}</p>
            </div>
            <div v-if="currentStep.status === 'failed'" class="step-error-summary">
              <strong>❌ 执行失败</strong>
              <p>{{ currentStep.error || '未知错误' }}</p>
            </div>
            <div v-else-if="currentStep.status === 'completed'" class="step-success">
              <strong>✅ 执行成功</strong>
            </div>
          </template>

          <!-- Developer Mode Display -->
          <template v-else>
            <div class="step-name">{{ getToolDisplayName(currentStep.name) }}</div>
            <div :class="['step-status', currentStep.status]">
              {{ currentStep.status }}
            </div>
            <div v-if="currentStep.tool" class="step-tool">
              <strong>工具：</strong> {{ getToolDisplayName(currentStep.tool) }}
            </div>
            <div v-if="currentStep.args" class="step-args">
              <strong>工具调用参数：</strong>
              <pre>{{ JSON.stringify(currentStep.args, null, 2) }}</pre>
            </div>
            <div v-if="currentStep.llmOutput" class="step-llm-output">
              <strong>LLM 原始输出（令牌流）：</strong>
              <pre class="llm-output">{{ currentStep.llmOutput }}</pre>
            </div>
            <div v-if="currentStep.result" class="step-result">
              <strong>结果：</strong>
              <pre>{{ typeof currentStep.result === 'string' ? currentStep.result : JSON.stringify(currentStep.result, null, 2) }}</pre>
            </div>
            <div v-if="currentStep.errorTraceback" class="step-error-traceback">
              <strong>错误堆栈：</strong>
              <pre class="traceback">{{ currentStep.errorTraceback }}</pre>
            </div>
            <div v-else-if="currentStep.error" class="step-error">
              <strong>错误：</strong>
              <pre>{{ currentStep.error }}</pre>
            </div>
          </template>
        </div>
      </div>

      <!-- Step History -->
      <div class="insight-section">
        <h3>步骤历史</h3>
        <div class="step-history">
          <div
            v-for="(step, index) in stepHistory"
            :key="step.id"
            :class="['step-item', step.status]"
          >
            <div class="step-item-header">
              <span class="step-number">{{ index + 1 }}</span>
              <span class="step-item-name">{{ viewMode === 'user' ? getToolDisplayName(step.name) : step.name }}</span>
              <span :class="['step-item-status', step.status]">
                {{ viewMode === 'user' ? getStatusLabel(step.status) : step.status }}
              </span>
            </div>
            
            <!-- User Mode: Show description and summary -->
            <template v-if="viewMode === 'user'">
              <div v-if="step.description" class="step-item-description">
                {{ step.description }}
              </div>
              <div v-if="step.resultSummary" class="step-item-summary">
                📋 {{ step.resultSummary }}
              </div>
              <div v-else-if="step.result && step.status === 'completed'" class="step-item-summary">
                📋 {{ formatResultSummary(step.result) }}
              </div>
              <div v-if="step.status === 'failed'" class="step-item-error">
                ❌ {{ step.error || '执行失败' }}
              </div>
            </template>
            
            <!-- Developer Mode: Show technical details -->
            <template v-else>
              <div v-if="step.tool" class="step-item-tool">
                🔧 {{ getToolDisplayName(step.tool) }}
              </div>
              <div v-if="step.args" class="step-item-args">
                <details>
                  <summary>参数</summary>
                  <pre>{{ JSON.stringify(step.args, null, 2) }}</pre>
                </details>
              </div>
              <div v-if="step.llmOutput" class="step-item-llm">
                <details>
                  <summary>LLM 输出</summary>
                  <pre class="llm-output">{{ step.llmOutput }}</pre>
                </details>
              </div>
              <div v-if="step.errorTraceback" class="step-item-traceback">
                <details>
                  <summary>错误堆栈</summary>
                  <pre class="traceback">{{ step.errorTraceback }}</pre>
                </details>
              </div>
              <div v-else-if="step.error" class="step-item-error">
                ⚠️ {{ step.error }}
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- Performance Metrics -->
      <div class="insight-section">
        <h3>性能指标</h3>
        <div class="metrics">
          <div class="metric-item">
            <div class="metric-label">平均步骤时间</div>
            <div class="metric-value">{{ formatDuration(performanceMetrics.avgStepTime) }}</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">成功率</div>
            <div class="metric-value">{{ performanceMetrics.successRate }}%</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">重试次数</div>
            <div class="metric-value">{{ performanceMetrics.retryCount }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';

interface TaskStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  tool?: string;
  args?: any;
  result?: any;
  error?: string;
  timestamp?: number;
  // User-friendly description of what the step is doing
  description?: string;
  // Summary of the result for users
  resultSummary?: string;
  // Developer mode fields
  llmOutput?: string; // LLM raw output (token stream)
  errorTraceback?: string; // Full error traceback for developers
}

interface TaskExecutionState {
  status: 'idle' | 'running' | 'completed' | 'failed' | 'paused';
  steps: TaskStep[];
  currentStepIndex: number;
  startTime?: number;
}

const props = defineProps<{
  taskExecutionState?: TaskExecutionState | null;
}>();

const emit = defineEmits<{
  (e: 'collapse-changed', collapsed: boolean): void;
}>();

const isCollapsed = ref(false);
const viewMode = ref<'user' | 'developer'>('user');

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value;
  emit('collapse-changed', isCollapsed.value);
};

const currentStep = computed(() => {
  if (!props.taskExecutionState) return null;
  return props.taskExecutionState.steps[props.taskExecutionState.currentStepIndex] || null;
});

const stepHistory = computed(() => {
  if (!props.taskExecutionState) return [];
  return props.taskExecutionState.steps;
});

const taskStats = computed(() => {
  if (!props.taskExecutionState) {
    return {
      totalSteps: 0,
      completedSteps: 0,
      failedSteps: 0,
      elapsedTime: 0,
    };
  }

  const steps = props.taskExecutionState.steps;
  const startTime = props.taskExecutionState.startTime || Date.now();
  
  return {
    totalSteps: steps.length,
    completedSteps: steps.filter(s => s.status === 'completed').length,
    failedSteps: steps.filter(s => s.status === 'failed').length,
    elapsedTime: Date.now() - startTime,
  };
});

const performanceMetrics = computed(() => {
  if (!props.taskExecutionState) {
    return {
      avgStepTime: 0,
      successRate: 0,
      retryCount: 0,
    };
  }

  const steps = props.taskExecutionState.steps;
  const completed = steps.filter(s => s.status === 'completed').length;
  const total = steps.length;
  
  // Calculate average step time (simplified)
  const avgStepTime = total > 0 ? (taskStats.value.elapsedTime / total) : 0;
  const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;
  
  // Count retries (steps that were retried)
  const retryCount = steps.filter(s => s.status === 'failed' && s.error).length;

  return {
    avgStepTime,
    successRate,
    retryCount,
  };
});

const formatDuration = (ms: number) => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return `${minutes}m ${seconds}s`;
};

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    'pending': '待执行',
    'running': '执行中',
    'completed': '已完成',
    'failed': '失败',
    'skipped': '已跳过',
  };
  return labels[status] || status;
};

const getToolDisplayName = (toolName: string): string => {
  const toolNames: Record<string, string> = {
    'file_parser': '文件解析',
    'web_search': '网络搜索',
    'github_repo_info': 'GitHub 仓库信息',
    'github_search_code': 'GitHub 代码搜索',
    'send_mail': 'QQ 邮件发送',
    'list_recent_mail': '最近邮件',
    'read_mail': '读取邮件',
    'add_calendar_event': '日历事件',
    'memory_search': '记忆检索',
    'memory_refresh': '记忆刷新',
    'plan_trip': '行程规划',
    'poi_search': '景点检索',
  };
  return toolNames[toolName] || toolName;
};

const formatResultSummary = (result: any): string => {
  if (typeof result === 'string') {
    // Truncate long strings
    return result.length > 100 ? result.substring(0, 100) + '...' : result;
  }
  if (typeof result === 'object' && result !== null) {
    // Try to extract meaningful summary
    if (result.summary) return result.summary;
    if (result.message) return result.message;
    if (result.data) {
      const dataStr = JSON.stringify(result.data);
      return dataStr.length > 100 ? dataStr.substring(0, 100) + '...' : dataStr;
    }
    const jsonStr = JSON.stringify(result);
    return jsonStr.length > 100 ? jsonStr.substring(0, 100) + '...' : jsonStr;
  }
  return String(result);
};

// Watch for task state changes to update start time
watch(() => props.taskExecutionState, (newState) => {
  if (newState && !newState.startTime) {
    newState.startTime = Date.now();
  }
}, { immediate: true });
</script>

<style scoped>
.task-insight-panel {
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
  transition: opacity 0.3s ease;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.mode-btn {
  padding: 0.4rem 0.75rem;
  border: none;
  background: transparent;
  color: #666;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.mode-btn:hover {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

.mode-btn.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 600;
}

.panel-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  white-space: nowrap;
  overflow: hidden;
}

.task-insight-panel.collapsed .panel-header h2 {
  display: none;
}

.collapse-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.collapse-btn:hover {
  background: rgba(102, 126, 234, 0.2);
  transform: scale(1.1);
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
}

.mode-toggle-section {
  margin-bottom: 1.5rem;
  display: flex;
  justify-content: center;
}

.mode-toggle {
  display: flex;
  gap: 0.25rem;
  background: rgba(255, 255, 255, 0.8);
  padding: 0.25rem;
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.insight-section {
  margin-bottom: 2rem;
}

.insight-section h3 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  font-weight: 700;
  color: #213547;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.stat-card {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
  padding: 1rem;
  border-radius: 12px;
  text-align: center;
  border: 1px solid rgba(102, 126, 234, 0.1);
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #667eea;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-size: 0.75rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.step-details {
  background: rgba(255, 255, 255, 0.8);
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.step-name {
  font-size: 1.1rem;
  font-weight: 600;
  color: #213547;
  margin-bottom: 0.5rem;
}

.step-status {
  display: inline-block;
  padding: 0.4rem 0.8rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 1rem;
}

.step-status.pending {
  background: rgba(158, 158, 158, 0.2);
  color: #616161;
}

.step-status.running {
  background: rgba(102, 126, 234, 0.2);
  color: #667eea;
}

.step-status.completed {
  background: rgba(66, 184, 131, 0.2);
  color: #42b883;
}

.step-status.failed {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.step-status.skipped {
  background: rgba(255, 152, 0, 0.2);
  color: #ff9800;
}

.step-tool,
.step-args,
.step-result,
.step-error {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}

.step-tool strong,
.step-args strong,
.step-result strong,
.step-error strong {
  display: block;
  margin-bottom: 0.25rem;
  color: #213547;
}

.step-args pre,
.step-result pre,
.step-error pre {
  background: rgba(0, 0, 0, 0.05);
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.8rem;
  overflow-x: auto;
  margin: 0.5rem 0 0 0;
  font-family: 'Courier New', monospace;
}

.step-error pre {
  background: rgba(244, 67, 54, 0.1);
  color: #f44336;
}

.step-description,
.step-result-summary {
  margin-top: 0.75rem;
  font-size: 0.9rem;
  line-height: 1.5;
  color: #213547;
}

.step-description p,
.step-result-summary p {
  margin: 0.5rem 0 0 0;
  padding: 0.5rem;
  background: rgba(102, 126, 234, 0.05);
  border-radius: 8px;
  border-left: 3px solid #667eea;
}

.step-error-summary {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(244, 67, 54, 0.1);
  border-radius: 8px;
  border-left: 3px solid #f44336;
  color: #f44336;
}

.step-error-summary p {
  margin: 0.5rem 0 0 0;
}

.step-success {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(66, 184, 131, 0.1);
  border-radius: 8px;
  border-left: 3px solid #42b883;
  color: #42b883;
}

.step-llm-output,
.step-error-traceback {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}

.step-llm-output strong,
.step-error-traceback strong {
  display: block;
  margin-bottom: 0.25rem;
  color: #213547;
}

.llm-output,
.traceback {
  background: rgba(0, 0, 0, 0.05);
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.75rem;
  overflow-x: auto;
  margin: 0.5rem 0 0 0;
  font-family: 'Courier New', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.traceback {
  background: rgba(244, 67, 54, 0.1);
  color: #f44336;
}

.step-item-description,
.step-item-summary {
  font-size: 0.8rem;
  color: #666;
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(102, 126, 234, 0.05);
  border-radius: 6px;
}

.step-item-args,
.step-item-llm,
.step-item-traceback {
  font-size: 0.75rem;
  margin-top: 0.5rem;
}

.step-item-args details,
.step-item-llm details,
.step-item-traceback details {
  cursor: pointer;
}

.step-item-args summary,
.step-item-llm summary,
.step-item-traceback summary {
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 6px;
  font-weight: 500;
  color: #213547;
}

.step-item-args pre,
.step-item-llm pre,
.step-item-traceback pre {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 6px;
  font-size: 0.7rem;
  overflow-x: auto;
  font-family: 'Courier New', monospace;
  max-height: 200px;
  overflow-y: auto;
}

.step-item-traceback pre {
  background: rgba(244, 67, 54, 0.1);
  color: #f44336;
}

.step-history {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.step-item {
  background: rgba(255, 255, 255, 0.8);
  padding: 0.75rem;
  border-radius: 8px;
  border-left: 3px solid #e0e0e0;
  font-size: 0.85rem;
}

.step-item.completed {
  border-left-color: #42b883;
}

.step-item.failed {
  border-left-color: #f44336;
}

.step-item.running {
  border-left-color: #667eea;
}

.step-item.skipped {
  border-left-color: #ff9800;
}

.step-item-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.step-number {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}

.step-item-name {
  flex: 1;
  font-weight: 500;
  color: #213547;
}

.step-item-status {
  padding: 0.25rem 0.5rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
}

.step-item-status.completed {
  background: rgba(66, 184, 131, 0.2);
  color: #42b883;
}

.step-item-status.failed {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.step-item-status.running {
  background: rgba(102, 126, 234, 0.2);
  color: #667eea;
}

.step-item-status.skipped {
  background: rgba(255, 152, 0, 0.2);
  color: #ff9800;
}

.step-item-tool {
  font-size: 0.75rem;
  color: #666;
  margin-top: 0.25rem;
}

.step-item-error {
  font-size: 0.75rem;
  color: #f44336;
  margin-top: 0.25rem;
  font-style: italic;
}

.metrics {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.metric-item {
  background: rgba(255, 255, 255, 0.8);
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.metric-label {
  font-size: 0.85rem;
  color: #666;
  margin-bottom: 0.5rem;
}

.metric-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #667eea;
}
</style>

