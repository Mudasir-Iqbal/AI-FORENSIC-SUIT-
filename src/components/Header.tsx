import { Shield } from 'lucide-react';

interface HeaderProps {
  demoMode: boolean;
  onToggleDemoMode: () => void;
}

export function Header({ demoMode, onToggleDemoMode }: HeaderProps) {
  return (
    <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <div className="flex items-center gap-3.5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-cyan-500/30 bg-gradient-to-br from-cyan-500/20 to-indigo-500/20 text-cyan-300">
            <Shield className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold tracking-tight text-slate-50 sm:text-xl">
              DeepGuard AI — Multi-Modal Content Detector
            </h1>
            <p className="text-sm text-slate-400">
              Analyze text, images, audio, and video for synthetic AI signatures.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 sm:justify-end shrink-0">
          <div className="flex items-center gap-3 rounded-xl border border-slate-800/90 bg-slate-900/70 px-3.5 py-2">
            <span
              id="demo-mode-label"
              className="text-sm font-medium text-slate-200 whitespace-nowrap"
            >
              Demo Mode
            </span>
            <button
              type="button"
              role="switch"
              aria-checked={demoMode}
              aria-labelledby="demo-mode-label"
              onClick={onToggleDemoMode}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 ${
                demoMode
                  ? 'border-cyan-400/50 bg-cyan-500'
                  : 'border-slate-700 bg-slate-800'
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
                  demoMode ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
