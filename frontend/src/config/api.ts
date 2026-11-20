import type { Modality } from '../types/detector';

function readEnvUrl(value: string | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

// Live endpoints are configured by the deployment environment.
// No third-party hosting URL is hardcoded into the frontend.
const configuredUrls: Record<Modality, string | null> = {
  text: readEnvUrl(import.meta.env.VITE_TEXT_API_URL),
  image: readEnvUrl(import.meta.env.VITE_IMAGE_API_URL),
  audio: readEnvUrl(import.meta.env.VITE_AUDIO_API_URL),
  video: readEnvUrl(import.meta.env.VITE_VIDEO_API_URL),
};

export const API_ENDPOINTS: Record<Modality, string> = {
  text: configuredUrls.text ?? '',
  image: configuredUrls.image ?? '',
  audio: configuredUrls.audio ?? '',
  video: configuredUrls.video ?? '',
};

export function isLiveEndpointConfigured(modality: Modality): boolean {
  return configuredUrls[modality] !== null;
}

export const hasAnyConfiguredEndpoint: boolean = Object.values(configuredUrls).some(
  (url) => url !== null
);
