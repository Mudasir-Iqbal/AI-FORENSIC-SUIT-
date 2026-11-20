import { AudioLines, FileText, Image as ImageIcon, Video } from 'lucide-react';
import type { ComponentType } from 'react';
import type { Modality } from '../types/detector';

interface ModalityTabsProps {
  activeModality: Modality;
  onSelectModality: (modality: Modality) => void;
  disabled?: boolean;
}

interface TabItem {
  id: Modality;
  label: string;
  icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean }>;
}

const TABS: TabItem[] = [
  { id: 'text', label: 'Text', icon: FileText },
  { id: 'image', label: 'Image', icon: ImageIcon },
  { id: 'audio', label: 'Audio', icon: AudioLines },
  { id: 'video', label: 'Video', icon: Video },
];

export function ModalityTabs({
  activeModality,
  onSelectModality,
  disabled = false,
}: ModalityTabsProps) {
  return (
    <div className="flex justify-center">
      <nav
        aria-label="Content Modality"
        role="tablist"
        className="grid w-full max-w-xl grid-cols-2 gap-1.5 rounded-2xl border border-slate-800/80 bg-slate-900/70 p-1.5 backdrop-blur-xl sm:grid-cols-4"
      >
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeModality === tab.id;

          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              disabled={disabled}
              onClick={() => onSelectModality(tab.id)}
              className={`flex min-h-[42px] items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium whitespace-nowrap shrink-0 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-60 ${
                isActive
                  ? 'border border-cyan-500/30 bg-gradient-to-r from-cyan-500/20 to-indigo-500/20 text-cyan-200 shadow-sm'
                  : 'border border-transparent text-slate-400 hover:bg-slate-800/60 hover:text-slate-100'
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden={true} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
