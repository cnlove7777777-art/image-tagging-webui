import axios from 'axios'
import type { Task, TaskBatchResponse, TaskImage } from '../types/task'

let apiBase = localStorage.getItem('apiBaseUrl') || '/api'

const api = axios.create({
  baseURL: apiBase,
  timeout: 30000
})

export interface ProviderModel {
  id: string
  label?: string
  tasks?: string[]
}

export interface ProviderInfo {
  id: string
  display_name?: string
  enabled?: boolean
  configured?: boolean
  base_url?: string
  api_format?: string
  source?: string
  dynamic_model_list?: boolean
  model_list_path?: string
  default_vision_model?: string
  default_focus_model?: string
  default_tag_model?: string
  models: ProviderModel[]
}

export interface ProviderRuntimeConfig {
  provider_id: string
  display_name?: string
  enabled?: boolean
  base_url?: string
  api_format?: string
  model_list_path?: string
  dynamic_model_list?: boolean
  api_key_masked?: string
  has_api_key?: boolean
  default_vision_model?: string
  default_focus_model?: string
  default_tag_model?: string
  models?: ProviderModel[]
}

export interface ProviderRuntimeConfigUpdate {
  display_name?: string
  enabled?: boolean
  base_url?: string
  api_key?: string
  api_format?: string
  model_list_path?: string
  dynamic_model_list?: boolean
  default_vision_model?: string
  default_focus_model?: string
  default_tag_model?: string
  models?: ProviderModel[]
}

export interface ProviderTestResult {
  ok: boolean
  provider_id: string
  url?: string
  status_code?: number
  model_count?: number | null
  sample_models?: string[]
  error?: string
}

export interface ModelList {
  default_provider?: string
  providers?: ProviderInfo[]
  focus_models: string[]
  tag_models: string[]
  default_focus_model: string
  default_tag_model: string
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
  crop_output_size: number
}

export interface LogEntry {
  id: number
  task_id: number
  level: string
  message: string
  created_at: string
}

export const setApiBaseUrl = (url: string) => {
  apiBase = url || '/api'
  api.defaults.baseURL = apiBase
  localStorage.setItem('apiBaseUrl', apiBase)
}

export const getApiBaseUrl = () => apiBase

const buildSseUrl = (path: string) => {
  if (apiBase.startsWith('http')) {
    return `${apiBase}${path}`
  }
  return `${apiBase}${path}`
}

export const getModels = async (refresh = false): Promise<ModelList> => {
  const response = await api.get<ModelList>('/models', { params: refresh ? { refresh: true } : undefined })
  return response.data
}

export const createProvider = async (payload: ProviderRuntimeConfigUpdate & { provider_id?: string; display_name: string }): Promise<ProviderRuntimeConfig> => {
  const response = await api.post<ProviderRuntimeConfig>('/models/providers', payload)
  return response.data
}

export const deleteProvider = async (providerId: string) => {
  const response = await api.delete(`/models/providers/${providerId}`)
  return response.data
}

export const getProviderRuntimeConfig = async (providerId: string): Promise<ProviderRuntimeConfig> => {
  const response = await api.get<ProviderRuntimeConfig>(`/models/providers/${providerId}/runtime-config`)
  return response.data
}

export const saveProviderRuntimeConfig = async (
  providerId: string,
  payload: ProviderRuntimeConfigUpdate
): Promise<ProviderRuntimeConfig> => {
  const response = await api.post<ProviderRuntimeConfig>(`/models/providers/${providerId}/runtime-config`, payload)
  return response.data
}

export const testProviderConnectivity = async (providerId: string, model?: string): Promise<ProviderTestResult> => {
  const response = await api.post<ProviderTestResult>(`/models/providers/${providerId}/test`, { model })
  return response.data
}

export const uploadTask = async (
  file: File,
  focus_model: string,
  tag_model: string,
  onUploadProgress?: (progressEvent: any) => void
): Promise<Task> => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('focus_model', focus_model)
  formData.append('tag_model', tag_model)

  const response = await api.post<Task>('/tasks', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress,
    timeout: 0
  })

  return response.data
}

export const uploadFolderTask = async (
  folderName: string,
  files: File[],
  focus_model: string,
  tag_model: string,
  onUploadProgress?: (progressEvent: any) => void
): Promise<Task> => {
  const formData = new FormData()

  files.forEach(file => {
    const relativePath = (file as any).webkitRelativePath || file.name
    formData.append('files', file, relativePath)
  })
  formData.append('folder_name', folderName)
  formData.append('focus_model', focus_model)
  formData.append('tag_model', tag_model)

  const response = await api.post<Task>('/tasks/folder', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress,
    timeout: 0
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

  files.forEach(file => {
    formData.append('files', file)
  })
  formData.append('focus_model', focus_model)
  formData.append('tag_model', tag_model)

  const response = await api.post<TaskBatchResponse[]>('/tasks/batch', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress,
    timeout: 0
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

export const deleteTask = async (taskId: number, force = true) => {
  return api.delete(`/tasks/${taskId}`, {
    params: force ? { force: true } : undefined,
    timeout: 0
  })
}

export const deleteAllTasks = async (force = true) => {
  return api.delete(`/tasks`, {
    params: force ? { force: true } : undefined,
    timeout: 0
  })
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

export const triggerRunAll = async (taskId: number, dedupParams?: any) => {
  return api.post(`/tasks/${taskId}/run-all`, dedupParams ?? undefined)
}

export const updateImageSelection = async (taskId: number, imageIds: number[], selected: boolean) => {
  return api.post(`/tasks/${taskId}/images/select`, { image_ids: imageIds, selected })
}

export const testSettings = async () => {
  const response = await api.post('/settings/test', {})
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
  if (Array.isArray(response.data)) {
    return response.data
  } else if ('value' in response.data && Array.isArray(response.data.value)) {
    return response.data.value
  }
  return []
}
