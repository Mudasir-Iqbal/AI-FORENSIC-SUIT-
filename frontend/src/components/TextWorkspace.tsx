import { ClipboardPaste, Eraser, ScanSearch } from 'lucide-react';
import { useState } from 'react';

interface TextWorkspaceProps {
  text: string;
  onChangeText: (value: string) => void;
  onAnalyze: () => void;
  isLoading: boolean;
}

const MAX_CHARACTERS = 10000;

const SAMPLE_PASSAGES = [
  'Moreover, the transformative landscape of modern algorithmic synthesis demonstrates an unprecedented capacity to orchestrate multifaceted narratives. Furthermore, leveraging comprehensive linguistic models enables organizations to delve into complex operational paradigms with remarkable precision and efficiency. In conclusion, these pivotal advancements continue to reshape digital communication across every contemporary industry.',
  'Yesterday morning I missed the 7:45 commuter train by thirty seconds because my coffee lid popped loose right on the stairwell. Instead of sprinting back upstairs, I grabbed a croissant from the corner bakery and waited twenty minutes on the cold platform watching freight cars roll through.',
];

export function TextWorkspace({
  text,
  onChangeText,
  onAnalyze,
  isLoading,
}: TextWorkspaceProps) {
  const [sampleIndex, setSampleIndex] = useState(0);
  const charCount = text.length;
  const isNearLimit = charCount >= MAX_CHARACTERS * 0.9;
  const canSubmit = text.trim().length > 0 && !isLoading;

  const handlePasteSample = () => {
    const nextSample = SAMPLE_PASSAGES[sampleIndex % SAMPLE_PASSAGES.length];
    onChangeText(nextSample.slice(0, MAX_CHARACTERS));
    setSampleIndex((prev) => prev + 1);
  };

  return (
    <div className="animate-panel-enter flex flex-col gap-5 rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-100 sm:text-lg">
            Text Analysis
          </h2>
          <p className="text-sm text-slate-400">
            Paste an article, essay, or message to evaluate whether it was written by a human or an LLM.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {text.length > 0 && (
            <button
              type="button"
              onClick={() => onChangeText('')}
              disabled={isLoading}
              className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl border border-slate-700/80 bg-slate-800/70 px-3 py-2 text-xs font-medium text-slate-300 whitespace-nowrap shrink-0 transition-colors hover:border-slate-600 hover:bg-slate-800 hover:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Eraser className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Clear</span>
            </button>
          )}
          <button
            type="button"
            onClick={handlePasteSample}
            disabled={isLoading}
            className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl border border-slate-700/80 bg-slate-800/70 px-3.5 py-2 text-xs font-medium text-cyan-200 whitespace-nowrap shrink-0 transition-colors hover:border-cyan-500/40 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ClipboardPaste className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Paste Sample Text</span>
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="detector-text-input" className="sr-only">
          Text content to analyze
        </label>
        <textarea
          id="detector-text-input"
          value={text}
          onChange={(e) => onChangeText(e.target.value.slice(0, MAX_CHARACTERS))}
          maxLength={MAX_CHARACTERS}
          rows={10}
          disabled={isLoading}
          placeholder="Paste or type text content here (minimum a few sentences recommended for accurate attribution)..."
          className="w-full resize-y rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-3.5 text-sm leading-relaxed text-slate-100 placeholder:text-slate-500 focus:border-cyan-500/60 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
        />

        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Supports up to 10,000 characters per scan</span>
          <span
            className={`font-mono tabular-nums ${
              isNearLimit ? 'text-amber-400' : 'text-slate-400'
            }`}
          >
            {charCount.toLocaleString()} / {MAX_CHARACTERS.toLocaleString()}
          </span>
        </div>
      </div>

      <div className="flex justify-end pt-1">
        <button
          type="button"
          onClick={onAnalyze}
          disabled={!canSubmit}
          className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 px-6 py-2.5 text-sm font-semibold text-slate-950 whitespace-nowrap shrink-0 transition-opacity duration-150 hover:opacity-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-45 sm:w-auto"
        >
          <ScanSearch className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>Analyze Text</span>
        </button>
      </div>
    </div>
  );
}
