export interface UploadFile {
  file: File
  taskId?: number
  progress: number
  status: 'pending' | 'uploading' | 'success' | 'error'
  message: string
  relativePath?: string
}
