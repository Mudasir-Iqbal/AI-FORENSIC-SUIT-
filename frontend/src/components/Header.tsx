import { Shield } from 'lucide-react';

export function Header() {
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

      </div>
    </header>
  );
}
