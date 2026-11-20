export type Modality = 'text' | 'image' | 'audio' | 'video' | 'url';

export interface DetectionApiResponse {
  ai_probability: number;
  is_ai_generated: boolean;
  label: string;
}

export interface DetectionResult extends DetectionApiResponse {
  modality: Modality;
  processingTimeMs: number;
  confidenceLevel: 'High' | 'Moderate' | 'Low';
  isDemo: boolean;
  riskScore?: number;
  finalUrl?: string | null;
  httpStatus?: number | null;
  redirectCount?: number;
  reasons?: string[];
  checks?: Array<{ name: string; status: string; detail: string }>;
}

export type AnalysisStatus = 'idle' | 'loading' | 'success' | 'error';

export interface AnalysisState {
  status: AnalysisStatus;
  result: DetectionResult | null;
  error: string | null;
}
