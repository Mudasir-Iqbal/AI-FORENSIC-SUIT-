import { API_ENDPOINTS, isLiveEndpointConfigured } from '../config/api';
import type {
  DetectionApiResponse,
  DetectionResult,
  Modality,
} from '../types/detector';

export interface AnalyzeRequest {
  modality: Modality;
  text?: string;
  file?: File | null;
  demoMode: boolean;
}

const DEMO_DELAY_MS = 1500;

function computeConfidenceLevel(probability: number): 'High' | 'Moderate' | 'Low' {
  const distanceFromThreshold = Math.abs(probability - 0.5);
  if (distanceFromThreshold >= 0.3) return 'High';
  if (distanceFromThreshold >= 0.15) return 'Moderate';
  return 'Low';
}

function hashString(input: string): number {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function simulateDemoResponse(
  modality: Modality,
  text?: string,
  file?: File | null
): DetectionApiResponse {
  if (modality === 'text' && text) {
    const normalized = text.toLowerCase();
    const aiMarkers = [
      'moreover', 'furthermore', 'in conclusion', 'delve', 'tapestry',
      'landscape', 'unprecedented', 'comprehensive', 'pivotal',
      'leveraging', 'transformative', 'orchestrate', 'multifaceted',
    ];
    const markerHits = aiMarkers.reduce(
      (count, marker) => (normalized.includes(marker) ? count + 1 : count),
      0
    );

    if (markerHits >= 2) {
      const prob = Math.min(0.97, 0.82 + markerHits * 0.03);
      return {
        ai_probability: Number(prob.toFixed(4)),
        is_ai_generated: true,
        label: 'Synthetic LLM Pattern Detected',
      };
    }

    const seed = hashString(text.slice(0, 240));
    const isAi = seed % 10 >= 6;
    const prob = isAi
      ? 0.72 + ((seed % 22) / 100)
      : 0.08 + ((seed % 24) / 100);

    return {
      ai_probability: Number(prob.toFixed(4)),
      is_ai_generated: isAi,
      label: isAi ? 'AI-Assisted Text Pattern' : 'Natural Human Composition',
    };
  }

  const fileSeedSource = file ? `${file.name}:${file.size}:${file.type}` : modality;
  const seed = hashString(fileSeedSource);
  const nameLower = (file?.name ?? '').toLowerCase();

  let isAi = seed % 2 === 0;
  if (['ai', 'gen', 'midjourney', 'sdxl', 'flux', 'deepfake', 'synth'].some((x) => nameLower.includes(x))) {
    isAi = true;
  } else if (['real', 'human', 'camera', 'raw', 'dsc', 'img_'].some((x) => nameLower.includes(x))) {
    isAi = false;
  }

  const aiProbability = isAi
    ? Number((0.76 + ((seed % 21) / 100)).toFixed(4))
    : Number((0.06 + ((seed % 23) / 100)).toFixed(4));

  const labelByModality: Record<Exclude<Modality, 'text'>, { ai: string; human: string }> = {
    image: { ai: 'Diffusion Artifact Signature', human: 'Authentic Camera Capture' },
    audio: { ai: 'Neural Vocoder Synthesis', human: 'Authentic Acoustic Recording' },
    video: { ai: 'Temporal Deepfake Artifacts', human: 'Authentic Video Stream' },
  };
  const labels = labelByModality[modality === 'text' ? 'image' : modality];

  return {
    ai_probability: aiProbability,
    is_ai_generated: isAi,
    label: isAi ? labels.ai : labels.human,
  };
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
  demoMode,
}: AnalyzeRequest): Promise<DetectionResult> {
  if (modality === 'text') {
    if (!text?.trim()) {
      throw new Error('Please enter or paste some text before running analysis.');
    }
  } else if (!file) {
    throw new Error(`Please upload a valid ${modality} file before running analysis.`);
  }

  const startedAt = performance.now();

  if (demoMode) {
    await new Promise((resolve) => setTimeout(resolve, DEMO_DELAY_MS));
    const simulated = simulateDemoResponse(modality, text, file);
    const processingTimeMs = Math.round(performance.now() - startedAt);
    return {
      ...simulated,
      modality,
      processingTimeMs,
      confidenceLevel: computeConfidenceLevel(simulated.ai_probability),
      isDemo: true,
    };
  }

  if (!isLiveEndpointConfigured(modality)) {
    throw new Error(
      `No live ${modality.toUpperCase()} API URL is configured. Set VITE_${modality.toUpperCase()}_API_URL in the deployment environment or enable Demo Mode.`
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

  const parsed = validateApiResponse(await response.json());
  const processingTimeMs = Math.round(performance.now() - startedAt);

  return {
    ...parsed,
    modality,
    processingTimeMs,
    confidenceLevel: computeConfidenceLevel(parsed.ai_probability),
    isDemo: false,
  };
}
