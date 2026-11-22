export type Modality = 'text' | 'image' | 'audio' | 'video' | 'url';

export interface DetectionApiResponse {
  ai_probability: number;
  is_ai_generated: boolean;
  label: string;
}

export interface VideoForensicsEvidence {
  examination_status: string;
  classification_status: string;
  classification_note: string;
  evidence_integrity: {
    original_filename: string;
    file_size_bytes: number;
    sha256: string;
    hash_algorithm: string;
    hash_scope: string;
  };
  video_metadata: {
    container: string | null;
    duration_seconds: number;
    width: number;
    height: number;
    frame_rate: number | null;
    video_codec: string | null;
    pixel_format: string | null;
    video_stream_count: number;
    audio_stream_count: number;
    audio_streams: Array<Record<string, unknown>>;
  };
  frame_sampling: {
    method: string;
    target_max_frames: number;
    sample_interval_seconds: number;
    sampled_frame_count: number;
    frame_hashes: Array<{
      sample_index: number;
      timestamp_seconds: number;
      frame_sha256: string;
      width: number;
      height: number;
      working_copy_format: string;
    }>;
  };
  analysis_tracks: Record<string, string>;
  evidence_handling: {
    original_modified: boolean;
    temporary_working_copy_used: boolean;
    temporary_files_deleted_after_analysis: boolean;
    persistent_evidence_storage: boolean;
    chain_of_custody_status: string;
  };
  limitations: string[];
}

export interface DetectionResult extends Omit<DetectionApiResponse, 'ai_probability' | 'is_ai_generated'> {
  ai_probability: number | null;
  is_ai_generated: boolean | null;
  modality: Modality;
  processingTimeMs: number;
  confidenceLevel: 'High' | 'Moderate' | 'Low';
  riskScore?: number;
  finalUrl?: string | null;
  httpStatus?: number | null;
  redirectCount?: number;
  reasons?: string[];
  checks?: Array<{ name: string; status: string; detail: string }>;
  modelId?: string;
  audioDurationSeconds?: number;
  sampleRate?: number;
  audioProbabilities?: { fake: number; real: number };
  imageWidth?: number;
  imageHeight?: number;
  imageProbabilities?: { ai: number; real: number };\n  videoForensics?: VideoForensicsEvidence;
}

export type AnalysisStatus = 'idle' | 'loading' | 'success' | 'error';

export interface AnalysisState {
  status: AnalysisStatus;
  result: DetectionResult | null;
  error: string | null;
}
