import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  ScanEye,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import type { AnalysisState, Modality } from '../types/detector';

interface ResultCardProps {
  state: AnalysisState;
  activeModality: Modality;
}

const MODALITY_NAMES: Record<Modality, string> = {
  text: 'Text',
  image: 'Image',
  audio: 'Audio',
  video: 'Video',
  url: 'URL',
};

export function ResultCard({
  state,
  activeModality,
}: ResultCardProps) {
  const { status, result, error } = state;

  return (
    <section
      aria-live="polite"
      aria-label="Detection Results"
      className="flex h-full flex-col justify-between rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl sm:p-6"
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
          <h2 className="text-base font-semibold text-slate-100 sm:text-lg">
            Detection Verdict
          </h2>
          <span className="text-xs font-medium text-slate-400">
            {MODALITY_NAMES[activeModality]} · Live API
          </span>
        </div>

        {status === 'idle' && (
          <div className="flex min-h-[260px] flex-col items-center justify-center gap-3 px-4 py-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-slate-800 bg-slate-950/70 text-slate-400">
              <ScanEye className="h-6 w-6" aria-hidden="true" />
            </div>
            <div className="max-w-xs space-y-1.5">
              <p className="text-sm font-medium text-slate-200">
                Ready for {MODALITY_NAMES[activeModality].toLowerCase()} verification
              </p>
              <p className="text-xs leading-relaxed text-slate-400">
                Submit content on the left to inspect the selected content type and review its analysis evidence.
              </p>
            </div>
          </div>
        )}

        {status === 'loading' && (
          <div className="flex min-h-[260px] flex-col items-center justify-center gap-4 px-4 py-8 text-center">
            <Loader2
              className="h-9 w-9 animate-spin text-cyan-400"
              aria-hidden="true"
            />
            <div className="space-y-1">
              <p className="text-sm font-medium text-slate-100">
                Analyzing content with AI models...
              </p>
              <p className="text-xs text-slate-400">
                Evaluating {MODALITY_NAMES[activeModality].toLowerCase()} signatures
              </p>
            </div>
            {activeModality === 'video' && (state.processingLog?.length ?? 0) > 0 && (
              <div className="w-full rounded-xl border border-slate-700 bg-slate-950/80 p-3 text-left">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-200">Live Video Processing</p>
                <ol className="space-y-3">
                  {state.processingLog?.map((entry, index) => (
                    <li key={`${entry.step}-${index}`} className="flex gap-3 text-xs">
                      <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${entry.status === 'completed' ? 'bg-emerald-500/15 text-emerald-300' : entry.status === 'blocked' ? 'bg-amber-500/15 text-amber-300' : 'bg-slate-800 text-slate-400'}`}>
                        {entry.status === 'completed' ? '✓' : entry.status === 'blocked' ? '×' : '·'}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-slate-200">{entry.step}</p>
                        <p className="mt-1 leading-relaxed text-slate-400">{entry.detail}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        )}

        {status === 'error' && (
          <div
            role="alert"
            className="animate-panel-enter flex items-start gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-rose-200"
          >
            <AlertCircle
              className="mt-0.5 h-5 w-5 shrink-0 text-rose-400"
              aria-hidden="true"
            />
            <div className="space-y-1">
              <p className="text-sm font-semibold text-rose-100">
                Analysis Failed
              </p>
              <p className="text-xs leading-relaxed text-rose-200/90">
                {error || 'Unable to complete analysis. Please verify your input and try again.'}
              </p>
            </div>
          </div>
        )}

        {status === 'success' && result && (
          <div className="animate-panel-enter flex flex-col gap-5">
            <div
              className={`flex items-center justify-between gap-4 rounded-xl border p-4 ${
                result.is_ai_generated === null
                  ? 'border-cyan-500/30 bg-cyan-500/10'
                  : result.is_ai_generated
                    ? 'border-rose-500/35 bg-rose-500/10'
                    : 'border-emerald-500/35 bg-emerald-500/10'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border ${
                    result.is_ai_generated === null
                      ? 'border-cyan-500/40 bg-cyan-500/20 text-cyan-300'
                      : result.is_ai_generated
                        ? 'border-rose-500/40 bg-rose-500/20 text-rose-300'
                        : 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300'
                  }`}
                >
                  {result.is_ai_generated === null ? (
                    <ScanEye className="h-5 w-5" aria-hidden="true" />
                  ) : result.is_ai_generated ? (
                    <ShieldAlert className="h-5 w-5" aria-hidden="true" />
                  ) : (
                    <ShieldCheck className="h-5 w-5" aria-hidden="true" />
                  )}
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-400">
                    Classification Verdict
                  </p>
                  <p
                    className={`text-base font-semibold ${
                      result.is_ai_generated ? 'text-rose-200' : 'text-emerald-200'
                    }`}
                  >
                    {result.modality === 'video' ? 'Video analysis completed' : result.modality === 'url' ? (result.is_ai_generated ? 'Potentially Suspicious' : 'No Major Indicators') : result.modality === 'audio' ? (result.is_ai_generated ? 'AI-Generated / Fake Audio' : 'Likely Real Audio') : result.modality === 'image' ? (result.is_ai_generated ? 'AI-Generated Image' : 'Likely Real Image') : (result.is_ai_generated ? 'AI Generated' : 'Human / Authentic')}
                  </p>
                </div>
              </div>

              <span
                className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold whitespace-nowrap shrink-0 ${
                  result.is_ai_generated === null
                    ? 'border-cyan-500/40 bg-cyan-500/20 text-cyan-200'
                    : result.is_ai_generated
                      ? 'border-rose-500/40 bg-rose-500/20 text-rose-200'
                      : 'border-emerald-500/40 bg-emerald-500/20 text-emerald-200'
                }`}
              >
                {result.is_ai_generated === null ? (
                  <ScanEye className="h-3.5 w-3.5" aria-hidden="true" />
                ) : result.is_ai_generated ? (
                  <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                <span>{result.modality === 'video' ? 'Review required' : result.modality === 'url' ? (result.is_ai_generated ? 'Risk Flagged' : 'Lower Risk') : (result.is_ai_generated ? 'Synthetic' : 'Authentic')}</span>
              </span>
            </div>

            {result.modality === 'video' && result.videoForensics && (
              <div className="space-y-4 rounded-2xl border border-cyan-400/25 bg-gradient-to-br from-slate-800/90 via-slate-900 to-slate-950 p-4 sm:p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="max-w-xl">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">Video analysis report</p>
                    <h3 className="mt-1 text-xl font-semibold text-white">Here is what we found</h3>
                    <p className="mt-1 text-sm leading-relaxed text-slate-300">The video was processed and the face-manipulation model completed its analysis. The scores below are model estimates, not a confirmed real-or-fake decision.</p>
                  </div>
                  <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1.5 text-xs font-semibold text-amber-200">Authenticity: Not assessed</span>
                </div>
                {result.videoForensics.gend_inference?.video_class_probabilities ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-3">
                        <p className="text-xs text-emerald-200/80">Real-class score</p>
                        <p className="mt-1 text-3xl font-bold tabular-nums text-emerald-300">{(result.videoForensics.gend_inference.video_class_probabilities.real * 100).toFixed(1)}<span className="text-lg">%</span></p>
                      </div>
                      <div className="rounded-xl border border-rose-400/20 bg-rose-400/5 p-3">
                        <p className="text-xs text-rose-200/80">Fake-class score</p>
                        <p className="mt-1 text-3xl font-bold tabular-nums text-rose-300">{(result.videoForensics.gend_inference.video_class_probabilities.fake * 100).toFixed(1)}<span className="text-lg">%</span></p>
                      </div>
                    </div>
                    <div className="h-3 overflow-hidden rounded-full bg-slate-700" role="img" aria-label={`Model score distribution: real ${(result.videoForensics.gend_inference.video_class_probabilities.real * 100).toFixed(1)} percent, fake ${(result.videoForensics.gend_inference.video_class_probabilities.fake * 100).toFixed(1)} percent`}>
                      <div className="flex h-full w-full">
                        <div className="h-full bg-emerald-400 transition-all" style={{ width: `${result.videoForensics.gend_inference.video_class_probabilities.real * 100}%` }} />
                        <div className="h-full bg-rose-400 transition-all" style={{ width: `${result.videoForensics.gend_inference.video_class_probabilities.fake * 100}%` }} />
                      </div>
                    </div>
                    <p className="text-xs leading-relaxed text-slate-400">These percentages show how the model distributed its scores between its two classes. They are not the probability that the video is genuinely real or fake.</p>
                  </div>
                ) : (
                  <div className="rounded-xl border border-amber-400/20 bg-amber-400/5 p-3 text-sm text-amber-100">{result.videoForensics.gend_inference?.reason ?? 'The video was inspected, but the model did not return usable classification scores.'}</div>
                )}
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="rounded-lg bg-slate-950/70 p-3"><p className="text-xs text-slate-400">Faces analyzed</p><p className="mt-1 text-lg font-semibold text-white">{result.videoForensics.gend_inference?.detected_face_frames ?? 0} <span className="text-xs font-normal text-slate-400">/ {result.videoForensics.gend_inference?.target_face_frames ?? 32} frames</span></p></div>
                  <div className="rounded-lg bg-slate-950/70 p-3"><p className="text-xs text-slate-400">Video length</p><p className="mt-1 text-lg font-semibold text-white">{result.videoForensics.video_metadata.duration_seconds.toFixed(1)}s</p></div>
                  <div className="rounded-lg bg-slate-950/70 p-3"><p className="text-xs text-slate-400">Video quality</p><p className="mt-1 text-lg font-semibold text-white">{result.videoForensics.video_metadata.width} × {result.videoForensics.video_metadata.height}</p></div>
                  <div className="rounded-lg bg-slate-950/70 p-3"><p className="text-xs text-slate-400">Total analysis</p><p className="mt-1 text-lg font-semibold text-white">{(result.processingTimeMs / 1000).toFixed(1)}s</p></div>
                </div>
                <div className="flex items-start gap-2 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden="true" />
                  <p className="text-xs leading-relaxed text-amber-100">Important: this model has not yet been independently calibrated for a reliable decision threshold. DeepGuard therefore reports the model scores but does not label this video as real or fake.</p>
                </div>
              </div>
            )}

            {result.modality !== 'video' && result.ai_probability !== null && (
            <div className="space-y-2.5">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-medium text-slate-300">
                  {result.modality === 'url' ? 'URL Risk Score' : result.modality === 'audio' ? 'Fake Audio Probability' : result.modality === 'image' ? 'AI Image Probability' : 'AI Probability Score'}
                </span>
                <span
                  className={`font-mono text-2xl font-bold tabular-nums ${
                    result.is_ai_generated ? 'text-rose-300' : 'text-emerald-300'
                  }`}
                >
                  {Math.round((result.ai_probability ?? 0) * 100)}%
                </span>
              </div>

              <div
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round((result.ai_probability ?? 0) * 100)}
                aria-label={result.modality === 'url' ? 'URL Risk Score' : 'AI Generation Probability'}
                className="h-3 w-full overflow-hidden rounded-full bg-slate-800"
              >
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    result.is_ai_generated
                      ? 'bg-gradient-to-r from-rose-500 to-rose-400'
                      : 'bg-gradient-to-r from-emerald-500 to-cyan-400'
                  }`}
                  style={{ width: `${Math.round((result.ai_probability ?? 0) * 100)}%` }}
                />
              </div>

              <div className="flex justify-between text-xs text-slate-500 font-mono tabular-nums">
                {result.modality === 'url' ? <><span>0% Low</span><span>40% Flag</span><span>100% High</span></> : <><span>0% Real</span><span>50% Threshold</span><span>100% AI</span></>}
              </div>
            </div>
            )}

            {result.modality !== 'video' && <div className="grid grid-cols-2 gap-3 border-t border-slate-800/80 pt-4 text-sm">
              <div className="space-y-0.5">
                <p className="text-xs text-slate-400">Modality Analyzed</p>
                <p className="font-medium text-slate-100">
                  {MODALITY_NAMES[result.modality]}
                </p>
              </div>
              <div className="space-y-0.5">
                <p className="text-xs text-slate-400">Processing Time</p>
                <p className="font-mono font-medium tabular-nums text-slate-100">
                  {(result.processingTimeMs / 1000).toFixed(2)}s
                </p>
              </div>
              <div className="space-y-0.5">
                <p className="text-xs text-slate-400">{result.modality === 'url' ? 'Risk Assessment' : result.modality === 'video' ? 'Classification' : 'Confidence Level'}</p>
                <p className="font-medium text-slate-100">
                  {result.modality === 'url' ? 'Heuristic' : result.modality === 'video' ? 'Not assessed yet' : result.confidenceLevel}
                </p>
              </div>
              <div className="space-y-0.5">
                <p className="text-xs text-slate-400">Signal Label</p>
                <p className="truncate font-medium text-slate-100" title={result.label}>
                  {result.label}
                </p>
              </div>
            </div>}

            {result.modality === "image" && (
              <div className="space-y-3 border-t border-slate-800/80 pt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Image Model Evidence</p>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><p className="text-xs text-slate-400">Image Dimensions</p><p className="font-mono text-slate-100">{result.imageWidth && result.imageHeight ? `${result.imageWidth} × ${result.imageHeight}` : "N/A"}</p></div>
                  <div><p className="text-xs text-slate-400">AI Probability</p><p className="font-mono text-rose-300">{result.imageProbabilities ? Math.round(result.imageProbabilities.ai * 100) + "%" : "N/A"}</p></div>
                  <div><p className="text-xs text-slate-400">Real Probability</p><p className="font-mono text-emerald-300">{result.imageProbabilities ? Math.round(result.imageProbabilities.real * 100) + "%" : "N/A"}</p></div>
                </div>
                <p className="break-all text-xs text-slate-500">Model: {result.modelId ?? "Image model"}</p>
                <p className="text-xs leading-relaxed text-slate-400">This classifier estimates whether an image resembles its training classes. New image generators, edits, screenshots, and heavy compression may affect results. Treat this as one forensic signal, not proof of authenticity.</p>
              </div>
            )}

            {result.modality === 'audio' && (
              <div className="space-y-3 border-t border-slate-800/80 pt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Audio Model Evidence</p>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-slate-400">Audio Duration</p>
                    <p className="font-mono text-slate-100">{result.audioDurationSeconds ?? 'N/A'}s</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Sample Rate</p>
                    <p className="font-mono text-slate-100">{result.sampleRate ? (result.sampleRate / 1000) + ' kHz' : 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Fake Probability</p>
                    <p className="font-mono text-rose-300">{result.audioProbabilities ? Math.round(result.audioProbabilities.fake * 100) + '%' : 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Real Probability</p>
                    <p className="font-mono text-emerald-300">{result.audioProbabilities ? Math.round(result.audioProbabilities.real * 100) + '%' : 'N/A'}</p>
                  </div>
                </div>
                <p className="break-all text-xs text-slate-500">Model: {result.modelId ?? 'Audio model'}</p>
                <p className="text-xs leading-relaxed text-slate-400">Model output is a classification estimate, not proof of audio authenticity. Performance can vary across languages, codecs, and recording conditions.</p>
              </div>
            )}

            {result.modality === 'video' && result.videoForensics && (
              <details className="group rounded-xl border border-slate-700 bg-slate-950/40">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-4 text-sm font-semibold text-slate-100 marker:hidden">
                  <span>Technical evidence and processing details</span>
                  <span className="text-xs font-normal text-cyan-300 group-open:hidden">Show details +</span>
                  <span className="hidden text-xs font-normal text-cyan-300 group-open:inline">Hide details −</span>
                </summary>
                <div className="space-y-4 border-t border-slate-800/80 p-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Video Forensic Intake</p>
                  <p className="mt-1 text-xs leading-relaxed text-cyan-200">{result.videoForensics.classification_note}</p>
                </div>
                <div className="rounded-xl border border-slate-700 bg-slate-950/80 p-3">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-200">Processing Log</p>
                  <ol className="space-y-3">
                    {result.videoForensics.processing_log.map((entry, index) => (
                      <li key={entry.step} className="flex gap-3 text-xs">
                        <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${entry.status === 'completed' ? 'bg-emerald-500/15 text-emerald-300' : entry.status === 'error' ? 'bg-rose-500/15 text-rose-300' : entry.status === 'blocked' ? 'bg-amber-500/15 text-amber-300' : 'bg-slate-800 text-slate-400'}`}>
                          {entry.status === 'completed' ? '✓' : entry.status === 'error' ? '!' : entry.status === 'blocked' ? '×' : '·'}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-medium text-slate-200">{index + 1}. {entry.step}</span>
                            <span className={`rounded px-2 py-0.5 text-[10px] uppercase tracking-wide ${entry.status === 'completed' ? 'bg-emerald-500/10 text-emerald-300' : entry.status === 'blocked' ? 'bg-amber-500/10 text-amber-300' : 'bg-slate-800 text-slate-400'}`}>{entry.status.replace('_', ' ')}</span>
                          </div>
                          <p className="mt-1 leading-relaxed text-slate-400">{entry.detail}</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
                {result.videoForensics.experimental_face_preprocessing && (
                  <div className="rounded-xl border border-cyan-500/25 bg-cyan-500/5 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-200">Experimental Face Screening</p>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                      <div><p className="text-slate-500">Detector</p><p className="text-slate-200">{result.videoForensics.experimental_face_preprocessing.detector}</p></div>
                      <div><p className="text-slate-500">Detected frames</p><p className="font-mono text-slate-200">{result.videoForensics.experimental_face_preprocessing.detected_frames} / {result.videoForensics.experimental_face_preprocessing.total_frames}</p></div>
                      <div><p className="text-slate-500">Aligned candidates</p><p className="font-mono text-slate-200">{result.videoForensics.experimental_face_preprocessing.aligned_frames}</p></div>
                      <div><p className="text-slate-500">GenD compatibility</p><p className="text-amber-200">Not validated</p></div>
                    </div>
                    <p className="mt-3 text-[11px] leading-relaxed text-slate-400">{result.videoForensics.experimental_face_preprocessing.warning ?? 'Experimental face crops are temporary and are not passed to GenD.'}</p>
                    {result.videoForensics.experimental_face_preprocessing.frames.some((frame) => frame.bounding_box_xyxy || frame.landmarks_5_xy) && (
                      <div className="mt-3 space-y-2 border-t border-slate-700/70 pt-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-300">Geometry Evidence · First 8 Frames</p>
                        {result.videoForensics.experimental_face_preprocessing.frames.filter((frame) => frame.bounding_box_xyxy || frame.landmarks_5_xy).slice(0, 8).map((frame) => (
                          <div key={frame.sample_index} className="rounded-lg bg-slate-950/70 p-2 text-[10px]">
                            <p className="font-medium text-slate-300">Frame {frame.sample_index + 1} · {frame.timestamp_seconds.toFixed(3)}s</p>
                            <p className="mt-1 break-all font-mono text-slate-400">Box ({frame.bounding_box_source ?? 'unknown'}): {frame.bounding_box_xyxy?.map((value) => value.toFixed(1)).join(', ') ?? 'N/A'}</p>
                            <p className="mt-1 break-all font-mono text-slate-500">5 landmarks (L-eye, R-eye, nose, L-mouth, R-mouth): {frame.landmarks_5_xy?.map(([x, y]) => x.toFixed(1) + ',' + y.toFixed(1)).join(' · ') ?? 'N/A'}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {result.videoForensics.experimental_yunet_preprocessing && (
                  <div className="rounded-xl border border-violet-500/25 bg-violet-500/5 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-200">Experimental YuNet Face Screening</p>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                      <div><p className="text-slate-500">Detector</p><p className="text-slate-200">{result.videoForensics.experimental_yunet_preprocessing.detector}</p></div>
                      <div><p className="text-slate-500">Detected frames</p><p className="font-mono text-slate-200">{result.videoForensics.experimental_yunet_preprocessing.detected_frames} / {result.videoForensics.experimental_yunet_preprocessing.total_frames}</p></div>
                      <div><p className="text-slate-500">Aligned candidates</p><p className="font-mono text-slate-200">{result.videoForensics.experimental_yunet_preprocessing.aligned_frames}</p></div>
                      <div><p className="text-slate-500">Detector license</p><p className="text-slate-200">{result.videoForensics.experimental_yunet_preprocessing.detector_license ?? 'Unspecified'}</p></div>
                      <div><p className="text-slate-500">Alignment geometry</p><p className="text-slate-200">{result.videoForensics.experimental_yunet_preprocessing.alignment_geometry ?? 'N/A'}</p></div>
                      <div><p className="text-slate-500">GenD compatibility</p><p className="text-amber-200">Not validated</p></div>
                    </div>
                    {result.videoForensics.experimental_yunet_preprocessing.model_sha256 && <p className="mt-2 break-all font-mono text-[10px] text-slate-500">Model SHA-256: {result.videoForensics.experimental_yunet_preprocessing.model_sha256}</p>}
                    <p className="mt-3 text-[11px] leading-relaxed text-slate-400">{result.videoForensics.experimental_yunet_preprocessing.warning ?? 'YuNet crops are temporary candidates and are not passed to GenD.'}</p>
                    {result.videoForensics.experimental_yunet_preprocessing.frames.some((frame) => frame.bounding_box_xyxy || frame.landmarks_5_xy) && (
                      <div className="mt-3 space-y-2 border-t border-slate-700/70 pt-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-300">Geometry Evidence · First 8 Frames</p>
                        {result.videoForensics.experimental_yunet_preprocessing.frames.filter((frame) => frame.bounding_box_xyxy || frame.landmarks_5_xy).slice(0, 8).map((frame) => (
                          <div key={frame.sample_index} className="rounded-lg bg-slate-950/70 p-2 text-[10px]">
                            <p className="font-medium text-slate-300">Frame {frame.sample_index + 1} · {frame.timestamp_seconds.toFixed(3)}s</p>
                            <p className="mt-1 break-all font-mono text-slate-400">Box ({frame.bounding_box_source ?? 'unknown'}): {frame.bounding_box_xyxy?.map((value) => value.toFixed(1)).join(', ') ?? 'N/A'}</p>
                            <p className="mt-1 break-all font-mono text-slate-500">5 landmarks (L-eye, R-eye, nose, L-mouth, R-mouth): {frame.landmarks_5_xy?.map(([x, y]) => x.toFixed(1) + ',' + y.toFixed(1)).join(' · ') ?? 'N/A'}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-200">GenD Model Input Gate</p>
                    <span className="rounded bg-amber-500/10 px-2 py-1 text-[10px] font-semibold uppercase text-amber-200">{result.videoForensics.model_input_gate.status}</span>
                  </div>
                  <p className="mt-2 break-all text-xs text-slate-400">Model: {result.videoForensics.model_input_gate.model_id}</p>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <div><p className="text-slate-500">Candidate frames</p><p className="font-mono text-slate-200">{result.videoForensics.model_input_gate.sampled_source_frames} / {result.videoForensics.model_input_gate.minimum_candidate_frames}</p></div>
                    <div><p className="text-slate-500">Required aligned crop</p><p className="font-mono text-slate-200">{result.videoForensics.model_input_gate.required_face_crop_size.join(' × ')}</p></div>
                    <div><p className="text-slate-500">Face alignment</p><p className="text-slate-200">5 landmarks · scale {result.videoForensics.model_input_gate.face_context_scale}</p></div>
                    <div><p className="text-slate-500">Runtime</p><p className="text-slate-200">{result.videoForensics.model_input_gate.model_runtime_status.replaceAll('_', ' ')}</p></div>
                  </div>
                  <ul className="mt-3 space-y-2">
                    {result.videoForensics.model_input_gate.blocking_reasons.map((reason, index) => (
                      <li key={index} className="flex gap-2 text-xs leading-relaxed text-amber-100"><span aria-hidden="true">•</span><span>{reason}</span></li>
                    ))}
                  </ul>
                  <p className="mt-3 text-[11px] leading-relaxed text-slate-400">Original upload remains unchanged. Official GenD inference uses its own upstream RetinaFace detector. Experimental MediaPipe and YuNet crops are not passed to GenD. No AI deblurring, generative upscaling or denoising is applied.</p>
                </div>
                {result.videoForensics.gend_inference && (
                  <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-100">Official GenD Model Evidence</p>
                      <span className={`rounded px-2 py-1 text-[10px] font-semibold uppercase ${result.videoForensics.gend_inference.status === 'official_preprocessing_and_inference_complete' ? 'bg-emerald-500/10 text-emerald-300' : 'bg-amber-500/10 text-amber-200'}`}>
                        {result.videoForensics.gend_inference.status.replaceAll('_', ' ')}
                      </span>
                    </div>
                    {result.videoForensics.gend_inference.video_class_probabilities ? (
                      <div className="mt-3 grid grid-cols-2 gap-3">
                        <div className="rounded-lg bg-slate-950/80 p-3">
                          <p className="text-xs text-slate-400">Real class score</p>
                          <p className="mt-1 font-mono text-2xl text-emerald-300">{(result.videoForensics.gend_inference.video_class_probabilities.real * 100).toFixed(2)}%</p>
                        </div>
                        <div className="rounded-lg bg-slate-950/80 p-3">
                          <p className="text-xs text-slate-400">Fake class score</p>
                          <p className="mt-1 font-mono text-2xl text-amber-300">{(result.videoForensics.gend_inference.video_class_probabilities.fake * 100).toFixed(2)}%</p>
                        </div>
                      </div>
                    ) : (
                      <p className="mt-3 text-xs leading-relaxed text-amber-100">{result.videoForensics.gend_inference.reason ?? 'GenD did not return an assessable score for this clip.'}</p>
                    )}
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                      <div><p className="text-slate-500">Model</p><p className="break-all text-slate-200">{result.videoForensics.gend_inference.model_id ?? 'GenD'}</p></div>
                      <div><p className="text-slate-500">Device</p><p className="text-slate-200">{result.videoForensics.gend_inference.device ?? 'N/A'}</p></div>
                      <div><p className="text-slate-500">Detected face frames</p><p className="font-mono text-slate-200">{result.videoForensics.gend_inference.detected_face_frames ?? 0} / {result.videoForensics.gend_inference.target_face_frames ?? 32}</p></div>
                      <div><p className="text-slate-500">Inference time</p><p className="font-mono text-slate-200">{result.videoForensics.gend_inference.processing_time_ms ?? 'N/A'} ms</p></div>
                    </div>
                    {result.videoForensics.gend_inference.model_revision && <p className="mt-2 break-all font-mono text-[10px] text-slate-500">Pinned revision: {result.videoForensics.gend_inference.model_revision}</p>}
                    {result.videoForensics.gend_inference.frame_evidence && result.videoForensics.gend_inference.frame_evidence.length > 0 && (
                      <div className="mt-3 space-y-2 border-t border-slate-700/70 pt-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-300">Per-frame GenD Evidence · First 8</p>
                        {result.videoForensics.gend_inference.frame_evidence.slice(0, 8).map((frame) => (
                          <div key={frame.source_frame_index} className="rounded-lg bg-slate-950/70 p-2 text-[10px]">
                            <div className="flex flex-wrap justify-between gap-2">
                              <span className="font-medium text-slate-300">Source frame {frame.source_frame_index}</span>
                              {frame.class_probabilities && <span className="font-mono text-cyan-200">Real {(frame.class_probabilities.real_class_0 * 100).toFixed(1)}% · Fake {(frame.class_probabilities.fake_class_1 * 100).toFixed(1)}%</span>}
                            </div>
                            <p className="mt-1 break-all font-mono text-slate-500">Aligned crop SHA-256: {frame.aligned_crop_sha256}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    <p className="mt-3 text-[11px] leading-relaxed text-amber-100">These are uncalibrated model scores, not confidence of authenticity or proof. The verdict remains Not Assessed until independent threshold validation.</p>
                    {result.videoForensics.gend_inference.research_only_detector_weight_license && <p className="mt-2 text-[10px] leading-relaxed text-slate-500">{result.videoForensics.gend_inference.research_only_detector_weight_license}</p>}
                  </div>
                )}
                <div className={`rounded-xl border p-3 ${result.videoForensics.quality_assessment.issues.length ? 'border-amber-500/30 bg-amber-500/5' : 'border-emerald-500/25 bg-emerald-500/5'}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-200">Input Quality Screening</p>
                    <span className="rounded bg-slate-800 px-2 py-1 text-[10px] uppercase text-slate-300">{result.videoForensics.quality_assessment.status.replaceAll('_', ' ')}</span>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <div><p className="text-slate-500">Sharpness*</p><p className="font-mono text-slate-200">{result.videoForensics.quality_assessment.mean_sharpness_proxy}</p></div>
                    <div><p className="text-slate-500">Brightness</p><p className="font-mono text-slate-200">{result.videoForensics.quality_assessment.mean_brightness}</p></div>
                    <div><p className="text-slate-500">Contrast</p><p className="font-mono text-slate-200">{result.videoForensics.quality_assessment.mean_contrast}</p></div>
                  </div>
                  {result.videoForensics.quality_assessment.issues.length > 0 ? (
                    <ul className="mt-3 space-y-2">
                      {result.videoForensics.quality_assessment.issues.map((issue) => (
                        <li key={issue.code} className="text-xs leading-relaxed text-amber-100">• {issue.message}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-3 text-xs text-emerald-200">No obvious blur, exposure or contrast warning was detected by the preliminary screening.</p>
                  )}
                  <p className="mt-3 text-[11px] leading-relaxed text-slate-500">{result.videoForensics.quality_assessment.metrics_method} These screening values do not certify that the GenD model requirements are met.</p>
                  <p className="mt-2 text-xs leading-relaxed text-slate-300">{result.videoForensics.quality_assessment.enhancement_note}</p>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><p className="text-xs text-slate-400">Duration</p><p className="font-mono text-slate-100">{result.videoForensics.video_metadata.duration_seconds}s</p></div>
                  <div><p className="text-xs text-slate-400">Resolution</p><p className="font-mono text-slate-100">{result.videoForensics.video_metadata.width} × {result.videoForensics.video_metadata.height}</p></div>
                  <div><p className="text-xs text-slate-400">Frame Rate</p><p className="font-mono text-slate-100">{result.videoForensics.video_metadata.frame_rate ?? 'Unknown'} FPS</p></div>
                  <div><p className="text-xs text-slate-400">Video Codec</p><p className="font-mono text-slate-100">{result.videoForensics.video_metadata.video_codec ?? 'Unknown'}</p></div>
                  <div><p className="text-xs text-slate-400">Audio Streams</p><p className="font-mono text-slate-100">{result.videoForensics.video_metadata.audio_stream_count}</p></div>
                  <div><p className="text-xs text-slate-400">Sampled Frames</p><p className="font-mono text-slate-100">{result.videoForensics.frame_sampling.sampled_frame_count}</p></div>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-400">Original File SHA-256</p>
                  <p className="break-all rounded-lg bg-slate-950 p-2 font-mono text-[11px] text-slate-200">{result.videoForensics.evidence_integrity.sha256}</p>
                  <p className="text-xs text-slate-500">{result.videoForensics.evidence_integrity.original_filename} · {result.videoForensics.evidence_integrity.file_size_bytes.toLocaleString()} bytes</p>
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Sampled Frame Evidence</p>
                  {result.videoForensics.frame_sampling.frame_hashes.slice(0, 8).map((frame) => (
                    <div key={frame.sample_index} className="rounded-lg border border-slate-800 bg-slate-950/70 p-2">
                      <div className="flex items-center justify-between gap-3 text-xs"><span className="font-medium text-slate-200">Frame #{frame.sample_index + 1}</span><span className="rounded bg-slate-800 px-2 py-1 font-mono tabular-nums text-cyan-200">Timestamp: {frame.timestamp_seconds.toFixed(3)} s</span></div>
                      <p className="mt-1 break-all font-mono text-[10px] text-slate-500">{frame.frame_sha256}</p>
                    </div>
                  ))}
                  {result.videoForensics.frame_sampling.sampled_frame_count > 8 && <p className="text-xs text-slate-500">Showing first 8 of {result.videoForensics.frame_sampling.sampled_frame_count} sampled frames. Full hashes are included in the API evidence response.</p>}
                </div>
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs leading-relaxed text-amber-100">
                  {result.videoForensics.gend_inference?.status === 'official_preprocessing_and_inference_complete' ? 'Official GenD face-manipulation inference completed. Its scores remain uncalibrated and no authenticity verdict is issued.' : 'Technical evidence intake completed, but GenD did not produce an assessable inference result. Classification remains Not Assessed.'} Temporary files are deleted after processing; persistent evidence storage and chain of custody are not established by this endpoint.
                </div>
                </div>
              </details>
            )}

            {result.modality === 'url' && (
              <div className="space-y-4 border-t border-slate-800/80 pt-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-slate-400">HTTP Status</p>
                    <p className="font-mono text-slate-100">{result.httpStatus ?? 'Unavailable'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Redirects Followed</p>
                    <p className="font-mono text-slate-100">{result.redirectCount ?? 0}</p>
                  </div>
                  {result.finalUrl && (
                    <div className="col-span-2 min-w-0">
                      <p className="text-xs text-slate-400">Final Destination</p>
                      <p className="break-all text-xs text-slate-200">{result.finalUrl}</p>
                    </div>
                  )}
                </div>
                {result.reasons && result.reasons.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-300">Evidence & Findings</p>
                    <ul className="space-y-2">
                      {result.reasons.map((reason, index) => (
                        <li key={index} className="flex gap-2 text-xs leading-relaxed text-slate-300">
                          <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                          {reason}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {result.checks && result.checks.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-300">Inspection Checks</p>
                    <ul className="space-y-2">
                      {result.checks.map((check, index) => (
                        <li key={index} className="flex items-start justify-between gap-3 text-xs">
                          <span className="text-slate-300">{check.name}</span>
                          <span className="text-right text-slate-400">{check.detail}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-6 border-t border-slate-800/70 pt-3 text-xs text-slate-500">
        Results are returned by the configured inference endpoint.
      </div>
    </section>
  );
}
