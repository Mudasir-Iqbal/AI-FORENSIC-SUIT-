import { Globe, ScanSearch } from 'lucide-react';

interface URLWorkspaceProps {
  url: string;
  onChangeURL: (value: string) => void;
  onAnalyze: () => void;
  isLoading: boolean;
}

export function URLWorkspace({ url, onChangeURL, onAnalyze, isLoading }: URLWorkspaceProps) {
  const canSubmit = url.trim().length > 0 && !isLoading;

  return (
    <section className="animate-panel-enter flex flex-col gap-5 rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl sm:p-6">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-cyan-500/20 bg-cyan-500/10 text-cyan-300">
          <Globe className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-100 sm:text-lg">URL Security Analysis</h2>
          <p className="mt-1 text-sm leading-relaxed text-slate-400">
            Inspect a website address for suspicious patterns, domain signals, HTTPS and redirect behavior.
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="detector-url-input" className="text-xs font-medium text-slate-300">Website URL</label>
        <input
          id="detector-url-input"
          type="url"
          value={url}
          onChange={(event) => onChangeURL(event.target.value)}
          disabled={isLoading}
          placeholder="https://example.com"
          autoComplete="url"
          className="min-h-[48px] w-full rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-cyan-500/60 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
        />
        <p className="text-xs leading-relaxed text-slate-500">
          Only public HTTP/HTTPS destinations are inspected. Private network and localhost targets are blocked.
        </p>
      </div>

      <div className="flex justify-end pt-1">
        <button
          type="button"
          onClick={onAnalyze}
          disabled={!canSubmit}
          className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 px-6 py-2.5 text-sm font-semibold text-slate-950 transition-opacity hover:opacity-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:cursor-not-allowed disabled:opacity-45 sm:w-auto"
        >
          <ScanSearch className="h-4 w-4" aria-hidden="true" />
          <span>Analyze URL</span>
        </button>
      </div>
    </section>
  );
}
