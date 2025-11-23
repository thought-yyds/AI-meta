/** API service for communicating with the backend. */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface Session {
  id: number;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string | null;
  message_count: number;
}

export interface Message {
  id: number;
  session_id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface Summary {
  id: number;
  session_id: number;
  content: string;
  message_count: number;
  created_at: string;
}

export interface ChatRequest {
  session_id?: number;
  message: string;
  context?: string;
}

export interface ExecutionStep {
  thought: string;
  action?: string;
  action_input?: Record<string, any>;
  observation?: Record<string, any>;
  timestamp?: string;
  context_info?: Record<string, any>;
}

export interface ChatResponse {
  session_id: number;
  message: Message;
  summary?: Summary;
  execution_steps?: ExecutionStep[];
}

class ApiService {
  private getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem('access_token');
    return {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
    };
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    
    // For FormData, don't set Content-Type (browser will set it with boundary)
    const isFormData = options.body instanceof FormData;
    const baseHeaders = isFormData 
      ? { ...(localStorage.getItem('access_token') && { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }) }
      : this.getAuthHeaders();
    
    const response = await fetch(url, {
      ...options,
      headers: {
        ...baseHeaders,
        ...options.headers,
      },
    });

    if (!response.ok) {
      // Handle 401 Unauthorized - token expired or invalid
      if (response.status === 401) {
        // Clear invalid token
        localStorage.removeItem('access_token');
        // Try to parse error message
        let errorMessage = '未授权：请重新登录';
        try {
          const contentType = response.headers.get('content-type');
          
          // Only try to read body if it's not a stream
          if (contentType && contentType.includes('application/json')) {
            try {
              const errorData = await response.json();
              if (errorData && typeof errorData === 'object') {
                errorMessage = errorData.detail || errorData.message || errorMessage;
              }
            } catch (jsonError) {
              // If JSON parsing fails, try text
              try {
                const text = await response.text();
                if (text && text.trim() && !text.includes('<') && !text.includes('object at') && text.length < 500) {
                  errorMessage = text;
                }
              } catch (textError) {
                // Use default message
              }
            }
          }
        } catch (e) {
          // If parsing fails, use default message
          console.warn('Failed to parse 401 error response:', e);
        }
        // Create a custom error that can be caught and handled
        const error = new Error(errorMessage);
        (error as any).status = 401;
        (error as any).requiresAuth = true;
        throw error;
      }

      // Handle other errors
      let errorMessage = `请求失败 (状态码: ${response.status})`;
      try {
        const contentType = response.headers.get('content-type');
        
        // Only try to read body if it's not a stream
        if (contentType && contentType.includes('application/json')) {
          try {
            const errorData = await response.json();
            if (errorData && typeof errorData === 'object') {
              errorMessage = errorData.detail || errorData.message || errorData.error || errorMessage;
            }
          } catch (jsonError) {
            // If JSON parsing fails, try text
            try {
              const text = await response.text();
              if (text && text.trim() && !text.includes('<') && !text.includes('object at') && text.length < 500) {
                errorMessage = text;
              }
            } catch (textError) {
              // Use default message based on status code
              if (response.status === 404) {
                errorMessage = '资源未找到';
              } else if (response.status === 403) {
                errorMessage = '没有权限访问此资源';
              } else if (response.status === 500) {
                errorMessage = '服务器内部错误';
              }
            }
          }
        } else {
          // Try to get text if not JSON
          try {
            const text = await response.text();
            if (text && text.trim() && !text.includes('<') && !text.includes('object at') && text.length < 500) {
              errorMessage = text;
            }
          } catch (textError) {
            // Use default message based on status code
            if (response.status === 404) {
              errorMessage = '资源未找到';
            } else if (response.status === 403) {
              errorMessage = '没有权限访问此资源';
            } else if (response.status === 500) {
              errorMessage = '服务器内部错误';
            }
          }
        }
      } catch (e) {
        // If parsing fails, use default message based on status code
        console.warn('Failed to parse error response:', e);
        if (response.status === 404) {
          errorMessage = '资源未找到';
        } else if (response.status === 403) {
          errorMessage = '没有权限访问此资源';
        } else if (response.status === 500) {
          errorMessage = '服务器内部错误';
        }
      }
      const error = new Error(errorMessage);
      (error as any).status = response.status;
      throw error;
    }

    // Handle empty responses
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      const text = await response.text();
      if (!text) {
        return {} as T;
      }
      return JSON.parse(text);
    }
    
    return response.json();
  }

  // Session endpoints
  async getSessions(): Promise<Session[]> {
    return this.request<Session[]>('/sessions/');
  }

  async getSession(sessionId: number): Promise<Session> {
    return this.request<Session>(`/sessions/${sessionId}`);
  }

  async createSession(title: string): Promise<Session> {
    return this.request<Session>('/sessions/', {
      method: 'POST',
      body: JSON.stringify({ title }),
    });
  }

  async updateSession(sessionId: number, title: string): Promise<Session> {
    return this.request<Session>(`/sessions/${sessionId}?title=${encodeURIComponent(title)}`, {
      method: 'PATCH',
    });
  }

  async deleteSession(sessionId: number): Promise<void> {
    return this.request<void>(`/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  }

  // Message endpoints
  async getMessages(sessionId: number): Promise<Message[]> {
    return this.request<Message[]>(`/messages/session/${sessionId}`);
  }

  // Chat endpoint
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>('/chat/', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Summary endpoints
  async getSummaries(sessionId: number): Promise<Summary[]> {
    return this.request<Summary[]>(`/summaries/session/${sessionId}`);
  }

  async generateSummary(sessionId: number): Promise<Summary> {
    return this.request<Summary>(`/summaries/session/${sessionId}/generate`, {
      method: 'POST',
    });
  }

  // Upload endpoints
  // Threshold for using chunked upload (50MB)
  private readonly CHUNKED_UPLOAD_THRESHOLD = 50 * 1024 * 1024;
  // Chunk size (5MB per chunk)
  private readonly CHUNK_SIZE = 5 * 1024 * 1024;

  async uploadFile(
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<{ filename: string; saved_filename: string; path: string; size: number; message: string }> {
    // For large files, use chunked upload
    if (file.size > this.CHUNKED_UPLOAD_THRESHOLD) {
      return this.uploadFileChunked(file, onProgress);
    }
    
    // For small files, use direct upload
    const formData = new FormData();
    formData.append('file', file);
    
    const token = localStorage.getItem('access_token');
    const url = `${API_BASE_URL}/uploads/`;
    
    // If progress callback is needed, use XMLHttpRequest (fetch doesn't support upload progress)
    if (onProgress) {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        
        // Track upload progress
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const progress = Math.round((e.loaded / e.total) * 100);
            onProgress(progress);
          }
        });
        
        xhr.addEventListener('load', () => {
          if (xhr.status === 201) {
            try {
              const result = JSON.parse(xhr.responseText);
              resolve(result);
            } catch (e) {
              reject(new Error('解析响应失败'));
            }
          } else if (xhr.status === 401) {
            localStorage.removeItem('access_token');
            const error = new Error('未授权：请重新登录');
            (error as any).status = 401;
            (error as any).requiresAuth = true;
            reject(error);
          } else {
            try {
              const errorData = JSON.parse(xhr.responseText);
              const error = new Error(errorData.detail || '上传失败');
              (error as any).status = xhr.status;
              reject(error);
            } catch (e) {
              const error = new Error('上传失败');
              (error as any).status = xhr.status;
              reject(error);
            }
          }
        });
        
        xhr.addEventListener('error', () => {
          reject(new Error('网络错误：上传失败'));
        });
        
        xhr.addEventListener('abort', () => {
          reject(new Error('上传已取消'));
        });
        
        xhr.open('POST', url);
        if (token) {
          xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        }
        xhr.send(formData);
      });
    }
    
    // Use fetch API when progress callback is not needed (cleaner, consistent with other methods)
    // request() method will automatically handle FormData and exclude Content-Type header
    return this.request<{ filename: string; saved_filename: string; path: string; size: number; message: string }>('/uploads/', {
      method: 'POST',
      body: formData,
    });
  }

  /**
   * Upload file using chunked upload for large files.
   * Supports resume on failure.
   */
  private async uploadFileChunked(
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<{ filename: string; saved_filename: string; path: string; size: number; message: string }> {
    const totalChunks = Math.ceil(file.size / this.CHUNK_SIZE);
    let uploadId: string;
    let uploadedChunks: number[] = [];

    try {
      // Step 1: Initialize upload
      const initFormData = new FormData();
      initFormData.append('filename', file.name);
      initFormData.append('file_size', file.size.toString());
      initFormData.append('total_chunks', totalChunks.toString());
      
      const initResponse = await this.request<{ upload_id: string; uploaded_chunks: number[] }>('/uploads/chunked/init', {
        method: 'POST',
        body: initFormData,
      });
      
      uploadId = initResponse.upload_id;
      uploadedChunks = initResponse.uploaded_chunks || [];

      // Step 2: Upload chunks (with retry logic)
      const chunksToUpload: number[] = [];
      for (let i = 0; i < totalChunks; i++) {
        if (!uploadedChunks.includes(i)) {
          chunksToUpload.push(i);
        }
      }

      // Upload chunks with concurrency control (max 3 concurrent uploads)
      const maxConcurrent = 3;
      let uploadedCount = uploadedChunks.length;

      const uploadChunk = async (chunkIndex: number): Promise<void> => {
        const start = chunkIndex * this.CHUNK_SIZE;
        const end = Math.min(start + this.CHUNK_SIZE, file.size);
        const chunkBlob = file.slice(start, end);

        const chunkFormData = new FormData();
        chunkFormData.append('upload_id', uploadId);
        chunkFormData.append('chunk_index', chunkIndex.toString());
        chunkFormData.append('chunk', chunkBlob, `chunk_${chunkIndex}`);

        try {
          await this.request<{ message: string; chunk_index: number; uploaded_chunks: number[]; progress: number }>('/uploads/chunked/chunk', {
            method: 'POST',
            body: chunkFormData,
          });

          // Update progress
          uploadedCount++;
          if (onProgress) {
            const progress = Math.round((uploadedCount / totalChunks) * 100);
            onProgress(progress);
          }
        } catch (error: any) {
          // Retry once on failure
          console.warn(`Chunk ${chunkIndex} upload failed, retrying...`, error);
          await this.request<{ message: string; chunk_index: number; uploaded_chunks: number[]; progress: number }>('/uploads/chunked/chunk', {
            method: 'POST',
            body: chunkFormData,
          });
          uploadedCount++;
          if (onProgress) {
            const progress = Math.round((uploadedCount / totalChunks) * 100);
            onProgress(progress);
          }
        }
      };

      // Upload chunks with concurrency control
      for (let i = 0; i < chunksToUpload.length; i += maxConcurrent) {
        const batch = chunksToUpload.slice(i, i + maxConcurrent);
        await Promise.all(batch.map(chunkIndex => uploadChunk(chunkIndex)));
      }

      // Step 3: Complete upload
      const completeFormData = new FormData();
      completeFormData.append('upload_id', uploadId);

      const result = await this.request<{ filename: string; saved_filename: string; path: string; size: number; message: string }>('/uploads/chunked/complete', {
        method: 'POST',
        body: completeFormData,
      });

      if (onProgress) {
        onProgress(100);
      }

      return result;
    } catch (error: any) {
      // If upload fails, the upload session can be resumed later
      throw error;
    }
  }

  async listUploadedFiles(): Promise<{ files: Array<{ filename: string; path: string; size: number; created_at: number }> }> {
    return this.request<{ files: Array<{ filename: string; path: string; size: number; created_at: number }> }>('/uploads/');
  }

  async deleteUploadedFile(filename: string): Promise<{ message: string; filename: string }> {
    return this.request<{ message: string; filename: string }>(`/uploads/${filename}`, {
      method: 'DELETE',
    });
  }
}

export const apiService = new ApiService();

