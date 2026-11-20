import {
  AudioLines,
  Image as ImageIcon,
  ScanSearch,
  Trash2,
  UploadCloud,
  Video,
} from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import type { ChangeEvent, DragEvent } from 'react';
import type { Modality } from '../types/detector';

type MediaModality = Exclude<Modality, 'text' | 'url'>;

interface MediaDropzoneProps {
  modality: MediaModality;
  file: File | null;
  onSelectFile: (file: File | null) => void;
  onAnalyze: () => void;
  isLoading: boolean;
}

interface ModalitySpec {
  title: string;
  subtitle: string;
  acceptAttr: string;
  extensions: string[];
  formatLabel: string;
  buttonLabel: string;
}

const MODALITY_SPECS: Record<MediaModality, ModalitySpec> = {
  image: {
    title: 'Image Analysis',
    subtitle: 'Upload a photograph or graphic to inspect for diffusion and GAN generation artifacts.',
    acceptAttr: '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp',
    extensions: ['.jpg', '.jpeg', '.png', '.webp'],
    formatLabel: 'JPG, JPEG, PNG, WEBP',
    buttonLabel: 'Analyze Image',
  },
  audio: {
    title: 'Audio Analysis',
    subtitle: 'Upload a voice recording or clip to check for neural vocoder and cloning signatures.',
    acceptAttr: '.mp3,.wav,.ogg,.m4a,audio/mpeg,audio/wav,audio/ogg,audio/mp4,audio/x-m4a',
    extensions: ['.mp3', '.wav', '.ogg', '.m4a'],
    formatLabel: 'MP3, WAV, OGG, M4A',
    buttonLabel: 'Analyze Audio',
  },
  video: {
    title: 'Video Analysis',
    subtitle: 'Upload a video clip to screen frame-level and temporal deepfake inconsistencies.',
    acceptAttr: '.mp4,.webm,.mov,video/mp4,video/webm,video/quicktime',
    extensions: ['.mp4', '.webm', '.mov'],
    formatLabel: 'MP4, WEBM, MOV',
    buttonLabel: 'Analyze Video',
  },
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(2)} MB`;
}

function isSupportedFile(file: File, extensions: string[]): boolean {
  const lowerName = file.name.toLowerCase();
  return extensions.some((ext) => lowerName.endsWith(ext));
}

export function MediaDropzone({
  modality,
  file,
  onSelectFile,
  onAnalyze,
  isLoading,
}: MediaDropzoneProps) {
  const inputId = useId();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const spec = MODALITY_SPECS[modality];

  useEffect(() => {
    setValidationError(null);
    setIsDragging(false);
  }, [modality]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [file]);

  const handleFileCandidate = (candidate: File | undefined) => {
    if (!candidate) return;
    if (!isSupportedFile(candidate, spec.extensions)) {
      setValidationError(
        `Unsupported file format. Please choose a ${spec.formatLabel} file.`
      );
      return;
    }
    setValidationError(null);
    onSelectFile(candidate);
  };

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    handleFileCandidate(e.target.files?.[0]);
    e.target.value = '';
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!isLoading) setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (isLoading) return;
    handleFileCandidate(e.dataTransfer.files?.[0]);
  };

  const handleRemove = () => {
    setValidationError(null);
    onSelectFile(null);
  };

  const ModalityIcon =
    modality === 'image' ? ImageIcon : modality === 'audio' ? AudioLines : Video;

  return (
    <div className="animate-panel-enter flex flex-col gap-5 rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl sm:p-6">
      <div>
        <h2 className="text-base font-semibold text-slate-100 sm:text-lg">
          {spec.title}
        </h2>
        <p className="text-sm text-slate-400">{spec.subtitle}</p>
      </div>

      <input
        ref={fileInputRef}
        id={inputId}
        type="file"
        accept={spec.acceptAttr}
        onChange={handleInputChange}
        disabled={isLoading}
        className="sr-only"
      />

      {!file ? (
        <div
          role="button"
          tabIndex={0}
          aria-label={`Upload ${modality} file`}
          onClick={() => !isLoading && fileInputRef.current?.click()}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !isLoading) {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`flex min-h-[256px] cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-10 text-center transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
            isDragging
              ? 'border-cyan-400 bg-cyan-500/10'
              : 'border-slate-700 bg-slate-950/50 hover:border-slate-500 hover:bg-slate-950/75'
          }`}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-slate-800 bg-slate-900 text-cyan-300">
            <UploadCloud className="h-6 w-6" aria-hidden="true" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-slate-200">
              Drag and drop your {modality} file here, or{' '}
              <span className="text-cyan-400 underline decoration-cyan-400/40 underline-offset-4">
                browse files
              </span>
            </p>
            <p className="text-xs text-slate-400">
              Accepted formats: {spec.formatLabel}
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-800 bg-slate-900 text-cyan-300">
                <ModalityIcon className="h-4 w-4" aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-100">
                  {file.name}
                </p>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <span className="inline-flex items-center rounded-md border border-slate-700/80 bg-slate-900 px-2 py-0.5 font-mono tabular-nums text-slate-300">
                    {formatFileSize(file.size)}
                  </span>
                  <span aria-hidden="true">·</span>
                  <span className="truncate">{file.type || modality.toUpperCase()}</span>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={handleRemove}
              disabled={isLoading}
              className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl border border-slate-700/80 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-300 whitespace-nowrap shrink-0 transition-colors hover:border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Remove</span>
            </button>
          </div>

          {previewUrl && modality === 'image' && (
            <div className="overflow-hidden rounded-lg border border-slate-800/80 bg-slate-950">
              <img
                src={previewUrl}
                alt={`Preview of ${file.name}`}
                className="mx-auto max-h-72 w-full object-contain"
              />
            </div>
          )}

          {previewUrl && modality === 'audio' && (
            <div className="rounded-lg border border-slate-800/80 bg-slate-900/70 p-4">
              <audio
                src={previewUrl}
                controls
                className="w-full"
                aria-label={`Audio preview for ${file.name}`}
              />
            </div>
          )}

          {previewUrl && modality === 'video' && (
            <div className="overflow-hidden rounded-lg border border-slate-800/80 bg-slate-950">
              <video
                src={previewUrl}
                controls
                className="mx-auto max-h-72 w-full"
                aria-label={`Video preview for ${file.name}`}
              />
            </div>
          )}
        </div>
      )}

      {validationError && (
        <p role="alert" className="text-sm text-rose-400">
          {validationError}
        </p>
      )}

      <div className="flex justify-end pt-1">
        <button
          type="button"
          onClick={onAnalyze}
          disabled={!file || isLoading}
          className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 px-6 py-2.5 text-sm font-semibold text-slate-950 whitespace-nowrap shrink-0 transition-opacity duration-150 hover:opacity-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-45 sm:w-auto"
        >
          <ScanSearch className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{spec.buttonLabel}</span>
        </button>
      </div>
    </div>
  );
}
