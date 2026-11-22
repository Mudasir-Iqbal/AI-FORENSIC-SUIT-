/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useRef, useState } from 'react';
import { Header } from './components/Header';
import { MediaDropzone } from './components/MediaDropzone';
import { ModalityTabs } from './components/ModalityTabs';
import { ResultCard } from './components/ResultCard';
import { TextWorkspace } from './components/TextWorkspace';
import { URLWorkspace } from './components/URLWorkspace';
import { analyzeContent } from './services/detectorApi';
import type { AnalysisState, Modality } from './types/detector';

type MediaFilesState = Record<Exclude<Modality, 'text' | 'url'>, File | null>;

const INITIAL_ANALYSIS_STATE: AnalysisState = {
  status: 'idle',
  result: null,
  error: null,
};

export default function App() {
  const [activeModality, setActiveModality] = useState<Modality>('text');
  const [textInput, setTextInput] = useState<string>('');
  const [urlInput, setUrlInput] = useState<string>('');
  const [mediaFiles, setMediaFiles] = useState<MediaFilesState>({
    image: null,
    audio: null,
    video: null,
  });
  const [analysisState, setAnalysisState] = useState<AnalysisState>(
    INITIAL_ANALYSIS_STATE
  );

  const requestIdRef = useRef(0);
  const isLoading = analysisState.status === 'loading';

  const handleSelectModality = (modality: Modality) => {
    if (modality === activeModality || isLoading) return;
    requestIdRef.current += 1;
    setActiveModality(modality);
    setAnalysisState(INITIAL_ANALYSIS_STATE);
  };

  const handleSelectMediaFile = (
    modality: Exclude<Modality, 'text' | 'url'>,
    file: File | null
  ) => {
    setMediaFiles((prev) => ({
      ...prev,
      [modality]: file,
    }));
    if (analysisState.status !== 'idle') {
      setAnalysisState(INITIAL_ANALYSIS_STATE);
    }
  };

  const handleAnalyze = async () => {
    const currentRequestId = requestIdRef.current + 1;
    requestIdRef.current = currentRequestId;

    setAnalysisState({
      status: 'loading',
      result: null,
      error: null,
      processingLog: [],
    });

    try {
      const result = await analyzeContent({
        modality: activeModality,
        text: activeModality === 'text' ? textInput : activeModality === 'url' ? urlInput : undefined,
        file: activeModality === 'text' || activeModality === 'url' ? null : mediaFiles[activeModality],
        onProgress: activeModality === 'video' ? (entry) => {
          if (requestIdRef.current !== currentRequestId) return;
          setAnalysisState((previous) => ({
            ...previous,
            processingLog: [...(previous.processingLog ?? []), entry],
          }));
        } : undefined,
      });

      if (requestIdRef.current !== currentRequestId) return;

      setAnalysisState({
        status: 'success',
        result,
        error: null,
      });
    } catch (err) {
      if (requestIdRef.current !== currentRequestId) return;

      const message =
        err instanceof Error
          ? err.message
          : 'An unexpected error occurred while analyzing content.';

      setAnalysisState({
        status: 'error',
        result: null,
        error: message,
      });
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col bg-slate-950 text-slate-100">
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(6,182,212,0.10),_transparent_55%)]"
      />

      <div className="relative z-10 flex min-h-screen flex-col">
        <Header />

        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
          <ModalityTabs
            activeModality={activeModality}
            onSelectModality={handleSelectModality}
            disabled={isLoading}
          />

          <div className="grid grid-cols-1 items-stretch gap-6 lg:grid-cols-12">
            <div className="lg:col-span-7">
              {activeModality === 'text' ? (
                <TextWorkspace
                  text={textInput}
                  onChangeText={(value) => {
                    setTextInput(value);
                    if (analysisState.status === 'error') setAnalysisState(INITIAL_ANALYSIS_STATE);
                  }}
                  onAnalyze={handleAnalyze}
                  isLoading={isLoading}
                />
              ) : activeModality === 'url' ? (
                <URLWorkspace
                  url={urlInput}
                  onChangeURL={(value) => {
                    setUrlInput(value);
                    if (analysisState.status === 'error') setAnalysisState(INITIAL_ANALYSIS_STATE);
                  }}
                  onAnalyze={handleAnalyze}
                  isLoading={isLoading}
                />
              ) : (
                <MediaDropzone
                  modality={activeModality}
                  file={mediaFiles[activeModality]}
                  onSelectFile={(file) => handleSelectMediaFile(activeModality, file)}
                  onAnalyze={handleAnalyze}
                  isLoading={isLoading}
                />
              )}
            </div>

            <div className="lg:col-span-5">
              <ResultCard
                state={analysisState}
                activeModality={activeModality}
              />
            </div>
          </div>
        </main>

        <footer className="border-t border-slate-900/90 py-4 text-center text-xs text-slate-500">
          DeepGuard AI · Multi-Modal Content Verification
        </footer>
      </div>
    </div>
  );
}
