import type { Modality } from '../types/detector';

const FALLBACK_DEMO_ENDPOINTS: Record<Modality, string> = {
  text: 'https://api-demo.deepguard.local/v1/detect/text',
  image: 'https://api-demo.deepguard.local/v1/detect/image',
  audio: 'https://api-demo.deepguard.local/v1/detect/audio',
  video: 'https://api-demo.deepguard.local/v1/detect/video',
};

function readEnvUrl(value: string | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

const configuredUrls: Record<Modality, string | null> = {
  text: readEnvUrl(import.meta.env.VITE_TEXT_API_URL),
  image: readEnvUrl(import.meta.env.VITE_IMAGE_API_URL),
  audio: readEnvUrl(import.meta.env.VITE_AUDIO_API_URL),
  video: readEnvUrl(import.meta.env.VITE_VIDEO_API_URL),
};

export const API_ENDPOINTS: Record<Modality, string> = {
  text: configuredUrls.text ?? FALLBACK_DEMO_ENDPOINTS.text,
  image: configuredUrls.image ?? FALLBACK_DEMO_ENDPOINTS.image,
  audio: configuredUrls.audio ?? FALLBACK_DEMO_ENDPOINTS.audio,
  video: configuredUrls.video ?? FALLBACK_DEMO_ENDPOINTS.video,
};

export function isLiveEndpointConfigured(modality: Modality): boolean {
  return configuredUrls[modality] !== null;
}

export const hasAnyConfiguredEndpoint: boolean = Object.values(configuredUrls).some(
  (url) => url !== null
);
