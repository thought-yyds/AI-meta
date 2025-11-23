<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1>AI Meta Chat</h1>
      <div v-if="isLogin" class="auth-form">
        <h2>登录</h2>
        <input
          v-model="username"
          type="text"
          placeholder="用户名"
          class="auth-input"
        />
        <input
          v-model="password"
          type="password"
          placeholder="密码"
          class="auth-input"
          @keydown.enter="login"
        />
        <button @click="login" :disabled="isLoading" class="auth-button">
          {{ isLoading ? '登录中...' : '登录' }}
        </button>
        <p class="auth-switch">
          还没有账号？
          <a @click="isLogin = false" href="#">注册</a>
        </p>
      </div>
      <div v-else class="auth-form">
        <h2>注册</h2>
        <input
          v-model="username"
          type="text"
          placeholder="用户名"
          class="auth-input"
        />
        <input
          v-model="email"
          type="email"
          placeholder="邮箱"
          class="auth-input"
        />
        <input
          v-model="password"
          type="password"
          placeholder="密码"
          class="auth-input"
          @keydown.enter="register"
        />
        <button @click="register" :disabled="isLoading" class="auth-button">
          {{ isLoading ? '注册中...' : '注册' }}
        </button>
        <p class="auth-switch">
          已有账号？
          <a @click="isLogin = true" href="#">登录</a>
        </p>
      </div>
      <p v-if="error" class="error-message">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const emit = defineEmits<{
  (e: 'authenticated'): void;
}>();

const isLogin = ref(true);
const username = ref('');
const email = ref('');
const password = ref('');
const isLoading = ref(false);
const error = ref('');

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const login = async () => {
  if (!username.value || !password.value) {
    error.value = '请填写所有字段';
    return;
  }

  isLoading.value = true;
  error.value = '';

  try {
    const formData = new FormData();
    formData.append('username', username.value);
    formData.append('password', password.value);

    const response = await fetch(`${API_BASE_URL}/auth/token`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      // 尝试解析错误响应
      let errorMessage = '登录失败';
      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } else {
          const text = await response.text();
          if (text && text.trim() && text.length < 500) {
            errorMessage = text;
          }
        }
      } catch (parseError) {
        // 如果解析失败，根据状态码提供默认消息
        if (response.status === 401) {
          errorMessage = '用户名或密码错误，请检查后重试';
        } else if (response.status === 404) {
          errorMessage = '登录接口未找到，请检查后端服务';
        } else if (response.status === 500) {
          errorMessage = '服务器错误，请稍后重试';
        } else {
          errorMessage = `登录失败 (状态码: ${response.status})`;
        }
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    if (!data.access_token) {
      throw new Error('服务器返回的响应格式不正确');
    }
    localStorage.setItem('access_token', data.access_token);
    emit('authenticated');
  } catch (err) {
    if (err instanceof Error) {
      error.value = err.message;
    } else {
      error.value = '登录失败，请检查网络连接';
    }
    console.error('Login error:', err);
  } finally {
    isLoading.value = false;
  }
};

const register = async () => {
  if (!username.value || !email.value || !password.value) {
    error.value = '请填写所有字段';
    return;
  }

  isLoading.value = true;
  error.value = '';

  try {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username.value,
        email: email.value,
        password: password.value,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '注册失败' }));
      throw new Error(errorData.detail || '注册失败');
    }

    // Wait a moment to ensure database transaction is committed
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // After registration, automatically log in
    await login();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '注册失败';
    isLoading.value = false;
  }
};
</script>

<style scoped>
.auth-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  position: relative;
  overflow: hidden;
}

.auth-container::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 1px, transparent 1px);
  background-size: 50px 50px;
  animation: moveBackground 20s linear infinite;
  pointer-events: none;
}

@keyframes moveBackground {
  0% {
    transform: translate(0, 0);
  }
  100% {
    transform: translate(50px, 50px);
  }
}

.auth-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  padding: 3rem;
  border-radius: 24px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  width: 100%;
  max-width: 420px;
  position: relative;
  z-index: 1;
  border: 1px solid rgba(255, 255, 255, 0.3);
  animation: slideUp 0.5s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.auth-card h1 {
  text-align: center;
  margin-bottom: 0.5rem;
  font-size: 2rem;
  font-weight: 800;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.auth-card h1::before {
  content: '💬';
  display: block;
  font-size: 3rem;
  margin-bottom: 0.5rem;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
}

.auth-form h2 {
  margin-bottom: 2rem;
  color: #213547;
  text-align: center;
  font-size: 1.5rem;
  font-weight: 700;
}

.auth-input {
  width: 100%;
  padding: 1rem;
  margin-bottom: 1rem;
  border: 2px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  font-size: 1rem;
  box-sizing: border-box;
  transition: all 0.2s ease;
  background: white;
}

.auth-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  transform: translateY(-1px);
}

.auth-input::placeholder {
  color: #999;
}

.auth-button {
  width: 100%;
  padding: 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: 1.5rem;
  transition: all 0.2s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
  position: relative;
  overflow: hidden;
}

.auth-button::before {
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

.auth-button:hover:not(:disabled)::before {
  width: 300px;
  height: 300px;
}

.auth-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
}

.auth-button:active:not(:disabled) {
  transform: translateY(0);
}

.auth-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.auth-switch {
  text-align: center;
  color: #666;
  font-size: 0.9rem;
  margin-top: 1rem;
}

.auth-switch a {
  color: #667eea;
  cursor: pointer;
  text-decoration: none;
  font-weight: 600;
  transition: all 0.2s ease;
  position: relative;
}

.auth-switch a::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 0;
  height: 2px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  transition: width 0.3s ease;
}

.auth-switch a:hover::after {
  width: 100%;
}

.error-message {
  color: #f44336;
  text-align: center;
  margin-top: 1rem;
  font-size: 0.9rem;
  padding: 0.75rem;
  background: rgba(244, 67, 54, 0.1);
  border-radius: 8px;
  border-left: 3px solid #f44336;
  animation: shake 0.5s ease;
}

@keyframes shake {
  0%, 100% {
    transform: translateX(0);
  }
  25% {
    transform: translateX(-10px);
  }
  75% {
    transform: translateX(10px);
  }
}

@media (max-width: 480px) {
  .auth-card {
    padding: 2rem 1.5rem;
    margin: 1rem;
    border-radius: 20px;
  }

  .auth-card h1 {
    font-size: 1.75rem;
  }

  .auth-form h2 {
    font-size: 1.25rem;
  }
}
</style>

