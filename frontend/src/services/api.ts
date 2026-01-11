import axios from 'axios'
import type { Task, TaskBatchResponse, TaskImage } from '../types/task'

let apiBase = localStorage.getItem('apiBaseUrl') || '/api'

const api = axios.create({
  baseURL: apiBase,
  timeout: 30000
})

export interface ApiSettings {
  base_url: string
  api_key: string
  model_priority?: string[]
  enabled: boolean
}

export interface DedupParams {
  face_sim_th1: number
  face_sim_th2: number
  pose_sim_th: number
  face_ssim_th1: number
  face_ssim_th2: number
  bbox_tol_c: number
  bbox_tol_wh: number
  keep_per_cluster: number
}

export interface ProcessingSettings {
  caption_prompt: string
  dedup_params: DedupParams
}

export interface LogEntry {
  id: number
  task_id: number
  level: string
  message: string
  created_at: string
}

const SETTINGS_KEY = 'ldb_api_settings'

export const loadApiSettings = (): ApiSettings => {
  const raw = localStorage.getItem(SETTINGS_KEY)
  if (!raw) return { base_url: '', api_key: '', model_priority: [], enabled: false }
  try {
    return { enabled: false, model_priority: [], ...JSON.parse(raw) }
  } catch {
    return { base_url: '', api_key: '', model_priority: [], enabled: false }
  }
}

export const saveApiSettings = (settings: ApiSettings) => {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
}

api.interceptors.request.use((config) => {
  const s = loadApiSettings()
  if (s.enabled) {
    if (!config.headers) {
      config.headers = new axios.AxiosHeaders()
    }
    if (s.base_url) {
      config.headers.set('X-Ext-Base-Url', s.base_url)
    }
    if (s.api_key) {
      config.headers.set('X-Ext-Api-Key', s.api_key)
    }
    if (s.model_priority && s.model_priority.length) {
      config.headers.set('X-Ext-Models', JSON.stringify(s.model_priority))
    }
  }
  return config
})

export const setApiBaseUrl = (url: string) => {
  apiBase = url || '/api'
  api.defaults.baseURL = apiBase
  localStorage.setItem('apiBaseUrl', apiBase)
}

export const getApiBaseUrl = () => apiBase

// 获取用户设置
const getAppSettings = () => {
  const settings = localStorage.getItem('appSettings')
  return settings ? JSON.parse(settings) : {}
}

const buildSseUrl = (path: string) => {
  if (apiBase.startsWith('http')) {
    return `${apiBase}${path}`
  }
  return `${apiBase}${path}`
}

// 模型列表类型
interface ModelList {
  focus_models: string[]
  tag_models: string[]
  default_focus_model: string
  default_tag_model: string
}

// 获取模型列表
export const getModels = async (): Promise<ModelList> => {
  const response = await api.get<ModelList>('/models')
  return response.data
}

export const uploadTask = async (
  file: File,
  focus_model: string,
  tag_model: string,
  onUploadProgress?: (progressEvent: any) => void
): Promise<Task> => {
  const formData = new FormData()
  const settings = getAppSettings()
  
  formData.append('file', file)
  formData.append('focus_model', focus_model)
  formData.append('tag_model', tag_model)
  
  // 添加API设置
  if (settings.apiKey) {
    formData.append('api_key', settings.apiKey)
  }
  if (settings.baseUrl) {
    formData.append('base_url', settings.baseUrl)
  }

  const response = await api.post<Task>('/tasks', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress
  })

  return response.data
}

export const uploadBatchTasks = async (
  files: File[],
  focus_model: string,
  tag_model: string,
  onUploadProgress?: (progressEvent: any) => void
): Promise<TaskBatchResponse[]> => {
  const formData = new FormData()
  const settings = getAppSettings()
  
  files.forEach(file => {
    formData.append('files', file)
  })
  formData.append('focus_model', focus_model)
  formData.append('tag_model', tag_model)
  
  // 添加API设置
  if (settings.apiKey) {
    formData.append('api_key', settings.apiKey)
  }
  if (settings.baseUrl) {
    formData.append('base_url', settings.baseUrl)
  }

  const response = await api.post<TaskBatchResponse[]>('/tasks/batch', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress
  })

  return response.data
}

export const getTasks = async (): Promise<Task[]> => {
  const response = await api.get<Task[]>('/tasks')
  return response.data
}

export const getTask = async (taskId: number): Promise<Task> => {
  const response = await api.get<Task>(`/tasks/${taskId}`)
  return response.data
}

export const downloadTask = async (taskId: number): Promise<void> => {
  const response = await api.get(`/tasks/${taskId}/download`, {
    responseType: 'blob'
  })

  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `task_${taskId}_result.zip`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

export const deleteTask = async (taskId: number) => {
  return api.delete(`/tasks/${taskId}`)
}

export const deleteAllTasks = async () => {
  return api.delete(`/tasks`)
}
export const getTaskImages = async (taskId: number, selected?: boolean): Promise<TaskImage[]> => {
  const params: any = {}
  if (selected !== undefined) params.selected = selected
  params.include_prompt = true
  const response = await api.get<TaskImage[]>(`/tasks/${taskId}/images`, { params })
  return response.data
}

export const createEventSource = (taskId: number, onMessage: (data: any) => void): EventSource => {
  const eventSource = new EventSource(buildSseUrl(`/tasks/${taskId}/events`))
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onMessage(data)
    } catch (error) {
      console.error('Error parsing SSE message:', error)
    }
  }
  
  eventSource.onerror = (error) => {
    console.error('SSE Error:', error)
    eventSource.close()
  }
  
  return eventSource
}

export const triggerDedup = async (taskId: number, dedupParams?: any) => {
  return api.post(`/tasks/${taskId}/dedup`, dedupParams || {})
}

export const triggerCrop = async (taskId: number) => {
  return api.post(`/tasks/${taskId}/crop`)
}

export const triggerCaption = async (taskId: number) => {
  return api.post(`/tasks/${taskId}/caption`)
}

export const triggerRunAll = async (taskId: number) => {
  return api.post(`/tasks/${taskId}/run-all`)
}

export const updateImageSelection = async (taskId: number, imageIds: number[], selected: boolean) => {
  return api.post(`/tasks/${taskId}/images/select`, { image_ids: imageIds, selected })
}

export const testSettings = async (settings?: ApiSettings) => {
  const s = settings ?? loadApiSettings()
  const headers: Record<string, string> = {}
  if (s.enabled) {
    if (s.base_url) headers['X-Ext-Base-Url'] = s.base_url
    if (s.api_key) headers['X-Ext-Api-Key'] = s.api_key
    if (s.model_priority && s.model_priority.length) {
      headers['X-Ext-Models'] = JSON.stringify(s.model_priority)
    }
  }
  const response = await api.post('/settings/test', {}, { headers })
  return response.data
}

export const getProcessingSettings = async (): Promise<ProcessingSettings> => {
  const response = await api.get<ProcessingSettings>('/settings')
  return response.data
}

export const updateProcessingSettings = async (payload: Partial<ProcessingSettings>) => {
  const response = await api.post<ProcessingSettings>('/settings', payload)
  return response.data
}

export const updateDecision = async (taskId: number, itemId: number, keep: boolean) => {
  return api.post(`/tasks/${taskId}/items/${itemId}/decision`, { keep })
}

export const updateCropSquare = async (taskId: number, itemId: number, crop_square: any) => {
  return api.post(`/tasks/${taskId}/items/${itemId}/crop`, { crop_square, source: 'user' })
}

export const getLogs = async (limit = 100): Promise<LogEntry[]> => {
  const response = await api.get<LogEntry[] | { value: LogEntry[] }>('/logs', { params: { limit } })
  // 检查返回数据格式，处理可能的包装
  if (Array.isArray(response.data)) {
    return response.data
  } else if ('value' in response.data && Array.isArray(response.data.value)) {
    return response.data.value
  }
  return []
}
