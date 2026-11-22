import { API_ENDPOINTS, isLiveEndpointConfigured } from '../config/api';
import type {
  DetectionApiResponse,
  DetectionResult,
  Modality,
  VideoForensicsEvidence,
} from '../types/detector';

export interface AnalyzeRequest {
  modality: Modality;
  text?: string;
  file?: File | null;
}

function computeConfidenceLevel(probability: number): 'High' | 'Moderate' | 'Low' {
  const distanceFromThreshold = Math.abs(probability - 0.5);
  if (distanceFromThreshold >= 0.3) return 'High';
  if (distanceFromThreshold >= 0.15) return 'Moderate';
  return 'Low';
}

function validateApiResponse(payload: unknown): DetectionApiResponse {
  if (!payload || typeof payload !== 'object') {
    throw new Error('Invalid response format received from detection API.');
  }

  const record = payload as Record<string, unknown>;
  const rawProbability = Number(record.ai_probability);
  if (!Number.isFinite(rawProbability) || rawProbability < 0 || rawProbability > 1) {
    throw new Error('API response is missing a valid ai_probability score.');
  }

  const aiProbability = rawProbability;
  const isAiGenerated =
    typeof record.is_ai_generated === 'boolean'
      ? record.is_ai_generated
      : aiProbability >= 0.5;
  const label =
    typeof record.label === 'string' && record.label.trim().length > 0
      ? record.label.trim()
      : isAiGenerated
        ? 'AI Generated'
        : 'Human / Authentic';

  return { ai_probability: aiProbability, is_ai_generated: isAiGenerated, label };
}

async function readApiError(response: Response): Promise<string> {
  let detail = `HTTP ${response.status} ${response.statusText}`;
  try {
    const body = (await response.json()) as {
      detail?: string | { message?: string };
      error?: string;
      message?: string;
    };
    if (typeof body.detail === 'string') detail = body.detail;
    else if (body.detail?.message) detail = body.detail.message;
    else detail = body.error || body.message || detail;
  } catch {
    // Keep the HTTP status when the endpoint does not return JSON.
  }
  return detail;
}

export async function analyzeContent({
  modality,
  text,
  file,
}: AnalyzeRequest): Promise<DetectionResult> {
  if (modality === 'text' || modality === 'url') {
    if (!text?.trim()) {
      throw new Error('Please enter a valid value before running analysis.');
    }
  } else if (!file) {
    throw new Error(`Please upload a valid ${modality} file before running analysis.`);
  }

  const startedAt = performance.now();

  if (!isLiveEndpointConfigured(modality)) {
    throw new Error(
      `No live ${modality.toUpperCase()} API URL is configured. Set VITE_${modality.toUpperCase()}_API_URL in the deployment environment.`
    );
  }

  const endpoint = API_ENDPOINTS[modality];
  let response: Response;

  try {
    if (modality === 'text') {
      response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text?.trim() ?? '' }),
      });
    } else if (modality === 'url') {
      response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: text?.trim() ?? '' }),
      });
    } else {
      const formData = new FormData();
      formData.append('file', file as File);
      response = await fetch(endpoint, { method: 'POST', body: formData });
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Network error while reaching the detection API.';
    throw new Error(`Connection failed: ${message}`);
  }

  if (!response.ok) {
    throw new Error(`Detection endpoint returned an error: ${await readApiError(response)}`);
  }

  const payload = await response.json();
  const processingTimeMs = Math.round(performance.now() - startedAt);

  if (modality === 'video') {
    const evidence = payload as VideoForensicsEvidence;
    if (
      !evidence ||
      evidence.examination_status !== 'evidence_prepared' ||
      !evidence.evidence_integrity?.sha256 ||
      !evidence.video_metadata ||
      !evidence.frame_sampling?.frame_hashes
    ) {
      throw new Error('Video forensic API returned an incomplete evidence package.');
    }
    return {
      ai_probability: null,
      is_ai_generated: null,
      label: 'Evidence Prepared · Classification Not Assessed',
      modality: 'video',
      processingTimeMs,
      confidenceLevel: 'Low',
      videoForensics: evidence,
    };
  }

  if (modality === 'url') {
    const record = payload as Record<string, unknown>;
    const riskScore = Number(record.risk_score);
    if (!Number.isFinite(riskScore) || riskScore < 0 || riskScore > 100) {
      throw new Error('URL API response is missing a valid risk_score.');
    }
    const isSuspicious = Boolean(record.is_suspicious);
    return {
      ai_probability: riskScore / 100,
      is_ai_generated: isSuspicious,
      label: typeof record.label === 'string' ? record.label : 'URL Risk Assessment',
      modality: 'url',
      processingTimeMs: Number(record.processing_time_ms) || processingTimeMs,
      confidenceLevel: computeConfidenceLevel(riskScore / 100),
      riskScore,
      finalUrl: typeof record.final_url === 'string' ? record.final_url : null,
      httpStatus: typeof record.http_status === 'number' ? record.http_status : null,
      redirectCount: Number(record.redirect_count) || 0,
      reasons: Array.isArray(record.reasons) ? record.reasons.filter((item): item is string => typeof item === 'string') : [],
      checks: Array.isArray(record.checks) ? record.checks as DetectionResult['checks'] : [],
    };
  }

  const parsed = validateApiResponse(payload);
  const record = payload as Record<string, unknown>;
  const audioProbabilities = record.probabilities && typeof record.probabilities === 'object'
    ? record.probabilities as Record<string, unknown>
    : null;
  return {
    ...parsed,
    modality,
    processingTimeMs: Number(record.processing_time_ms) || processingTimeMs,
    confidenceLevel: computeConfidenceLevel(parsed.ai_probability),
    ...(modality === 'image' ? {
      modelId: typeof record.model_id === 'string' ? record.model_id : undefined,
      imageWidth: typeof record.image_width === 'number' ? record.image_width : undefined,
      imageHeight: typeof record.image_height === 'number' ? record.image_height : undefined,
      imageProbabilities: record.probabilities && typeof record.probabilities === 'object'
        ? { ai: Number((record.probabilities as Record<string, unknown>).ai) || 0, real: Number((record.probabilities as Record<string, unknown>).real) || 0 }
        : undefined,
    } : {}),
    ...(modality === 'audio' ? {
      modelId: typeof record.model_id === 'string' ? record.model_id : undefined,
      audioDurationSeconds: typeof record.audio_duration_seconds === 'number' ? record.audio_duration_seconds : undefined,
      sampleRate: typeof record.sample_rate === 'number' ? record.sample_rate : undefined,
      audioProbabilities: audioProbabilities
        ? { fake: Number(audioProbabilities.fake) || 0, real: Number(audioProbabilities.real) || 0 }
        : undefined,
    } : {}),
  };
}
