export interface Task {
  id: number
  name: string
  status: 'uploading' | 'pending' | 'processing' | 'completed' | 'error'
  stage: 'initial' | 'unpacking' | 'de_duplication' | 'preview_generation' | 'focus_detection' | 'cropping' | 'tagging' | 'packaging' | 'finished'
  progress: number
  message: string
  progress_detail: {
    overall_percent: number
    stage_index: number
    stage_total: number
    stage_name: string
    stage_percent: number
    step_hint?: string
  }
  created_at: string
  updated_at: string
  focus_model: string
  tag_model: string
  stats: {
    total_files: number
    image_files: number
    kept_files: number
    processed_files: number
  }
  upload_path?: string
  export_path?: string
  export_ready?: boolean
  items?: TaskImage[]
  config?: Record<string, any>
}

export interface TaskImage {
  id: number
  task_id: number
  orig_name: string
  orig_path?: string | null
  preview_path?: string | null
  crop_path?: string | null
  prompt_txt_path?: string | null
  md5?: string
  phash?: string
  sharpness?: number
  width?: number
  height?: number
  selected: boolean
  meta_json: any
  preview_url?: string | null
  crop_url?: string | null
  has_prompt: boolean
  prompt_text?: string
  subject_area_ratio?: number
  has_face?: boolean
  face_conf?: number
  has_pose?: boolean
  pose_conf?: number
  shot_type?: string
  confidence?: number
  reason?: string
  cluster_id?: string | number
  quality?: {
    usable?: boolean
    reject_reason?: string
  }
  crop_square_model?: any
  crop_square_user?: any
  decision?: {
    keep?: boolean
  }
}

export interface TaskCreate {
  focus_model?: string
  tag_model?: string
}

export interface TaskBatchResponse {
  id: number
  zip_name: string
}
