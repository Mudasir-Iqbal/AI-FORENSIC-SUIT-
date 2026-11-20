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
  demoMode: boolean;
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
  demoMode,
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
            {MODALITY_NAMES[activeModality]} · {demoMode && activeModality !== 'url' ? 'Demo Simulation' : 'Live API'}
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
                result.is_ai_generated
                  ? 'border-rose-500/35 bg-rose-500/10'
                  : 'border-emerald-500/35 bg-emerald-500/10'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border ${
                    result.is_ai_generated
                      ? 'border-rose-500/40 bg-rose-500/20 text-rose-300'
                      : 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300'
                  }`}
                >
                  {result.is_ai_generated ? (
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
                    {result.modality === 'url' ? (result.is_ai_generated ? 'Potentially Suspicious' : 'No Major Indicators') : (result.is_ai_generated ? 'AI Generated' : 'Human / Authentic')}
                  </p>
                </div>
              </div>

              <span
                className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold whitespace-nowrap shrink-0 ${
                  result.is_ai_generated
                    ? 'border-rose-500/40 bg-rose-500/20 text-rose-200'
                    : 'border-emerald-500/40 bg-emerald-500/20 text-emerald-200'
                }`}
              >
                {result.is_ai_generated ? (
                  <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                <span>{result.modality === 'url' ? (result.is_ai_generated ? 'Risk Flagged' : 'Lower Risk') : (result.is_ai_generated ? 'Synthetic' : 'Authentic')}</span>
              </span>
            </div>

            <div className="space-y-2.5">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-medium text-slate-300">
                  {result.modality === 'url' ? 'URL Risk Score' : 'AI Probability Score'}
                </span>
                <span
                  className={`font-mono text-2xl font-bold tabular-nums ${
                    result.is_ai_generated ? 'text-rose-300' : 'text-emerald-300'
                  }`}
                >
                  {Math.round(result.ai_probability * 100)}%
                </span>
              </div>

              <div
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(result.ai_probability * 100)}
                aria-label={result.modality === 'url' ? 'URL Risk Score' : 'AI Generation Probability'}
                className="h-3 w-full overflow-hidden rounded-full bg-slate-800"
              >
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    result.is_ai_generated
                      ? 'bg-gradient-to-r from-rose-500 to-rose-400'
                      : 'bg-gradient-to-r from-emerald-500 to-cyan-400'
                  }`}
                  style={{ width: `${Math.round(result.ai_probability * 100)}%` }}
                />
              </div>

              <div className="flex justify-between text-xs text-slate-500 font-mono tabular-nums">
                {result.modality === 'url' ? <><span>0% Low</span><span>40% Flag</span><span>100% High</span></> : <><span>0% Human</span><span>50% Threshold</span><span>100% AI</span></>}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 border-t border-slate-800/80 pt-4 text-sm">
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
                <p className="text-xs text-slate-400">{result.modality === 'url' ? 'Risk Assessment' : 'Confidence Level'}</p>
                <p className="font-medium text-slate-100">
                  {result.modality === 'url' ? 'Heuristic' : result.confidenceLevel}
                </p>
              </div>
              <div className="space-y-0.5">
                <p className="text-xs text-slate-400">Signal Label</p>
                <p className="truncate font-medium text-slate-100" title={result.label}>
                  {result.label}
                </p>
              </div>
            </div>

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
        {result?.isDemo || (demoMode && activeModality !== 'url')
          ? 'Demo Mode simulates backend model responses locally with a 1.5s latency.'
          : 'Connected to configured inference endpoint.'}
      </div>
    </section>
  );
}
