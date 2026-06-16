import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import { BslEditor } from '../../components/BslEditor';
import { swarmApi } from '../../lib/api-client';
import { Code, Play, Save, Settings, FileCode, FolderOpen, Terminal, AlertTriangle } from 'lucide-react';

export const Route = createFileRoute('/_authenticated/ide')({
  component: IdePage,
});

function IdePage() {
  const [activeTab, setActiveTab] = useState('module.bsl');
  const [showProblems, setShowProblems] = useState(false);
  const [reviewResult, setReviewResult] = useState<{
    decision: string;
    scores: Record<string, number>;
    response: string | null;
    confidence: number;
  } | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [editorCode, setEditorCode] = useState<string | undefined>(undefined);

  const handleReview = async () => {
    if (!editorCode) return;
    setReviewing(true);
    try {
      const { data } = await swarmApi.review(editorCode);
      setReviewResult(data);
      setShowProblems(true);
    } catch {
      setReviewResult(null);
    } finally {
      setReviewing(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-slate-700 bg-slate-900 px-4 py-2">
        <div className="flex items-center gap-3">
          <Code className="h-5 w-5 text-blue-400" />
          <h1 className="text-sm font-semibold text-slate-200">1C:IDE</h1>
          <span className="text-xs text-slate-500">BSL Editor</span>
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-1.5 rounded-md bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 transition-colors">
            <FolderOpen className="h-3.5 w-3.5" />
            Open
          </button>
          <button className="flex items-center gap-1.5 rounded-md bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 transition-colors">
            <Save className="h-3.5 w-3.5" />
            Save
          </button>
          <button 
            className="flex items-center gap-1.5 rounded-md bg-green-900/50 px-3 py-1.5 text-xs text-green-300 hover:bg-green-800/50 transition-colors"
            onClick={handleReview}
            disabled={reviewing}
          >
            <Play className="h-3.5 w-3.5" />
            {reviewing ? 'Analyzing...' : 'Review'}
          </button>
          <button className="flex items-center gap-1.5 rounded-md bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 transition-colors">
            <Settings className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex items-center border-b border-slate-700 bg-slate-900/50">
        <button
          className={`flex items-center gap-1.5 px-4 py-2 text-xs border-b-2 transition-colors ${
            activeTab === 'module.bsl'
              ? 'border-blue-400 text-blue-300 bg-slate-800/50'
              : 'border-transparent text-slate-500 hover:text-slate-300'
          }`}
          onClick={() => setActiveTab('module.bsl')}
        >
          <FileCode className="h-3.5 w-3.5" />
          module.bsl
        </button>
      </div>

      {/* Editor area */}
      <div className="flex-1 min-h-0">
        <BslEditor onChange={(val) => setEditorCode(val)} />
      </div>

      {/* Bottom panel (problems/terminal toggle) */}
      <div className="border-t border-slate-700 bg-slate-900">
        <div className="flex items-center gap-4 px-4 py-1.5">
          <button
            className={`flex items-center gap-1.5 text-xs transition-colors ${
              showProblems ? 'text-blue-300' : 'text-slate-500 hover:text-slate-300'
            }`}
            onClick={() => setShowProblems(!showProblems)}
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            Problems
            <span className="rounded-full bg-slate-700 px-1.5 text-[10px]">
              {reviewResult ? Object.values(reviewResult.scores).filter(s => s > 0.3).length : 0}
            </span>
          </button>
          <button className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors">
            <Terminal className="h-3.5 w-3.5" />
            Output
          </button>
        </div>
        {showProblems && (
          <div className="border-t border-slate-700 px-4 py-3 text-xs h-32 overflow-auto">
            {reviewResult ? (
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <span className={`font-semibold ${
                    reviewResult.decision === 'clean' ? 'text-green-400' :
                    reviewResult.decision === 'template' ? 'text-yellow-400' : 'text-red-400'
                  }`}>
                    {reviewResult.decision.toUpperCase()}
                  </span>
                  <span className="text-slate-500">
                    Confidence: {(reviewResult.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                {Object.entries(reviewResult.scores).map(([domain, score]) => (
                  <div key={domain} className="flex items-center gap-2">
                    <span className="text-slate-400 w-32">{domain}</span>
                    <div className="flex-1 bg-slate-700 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full ${score > 0.7 ? 'bg-red-500' : score > 0.3 ? 'bg-yellow-500' : 'bg-green-500'}`}
                        style={{ width: `${Math.max(score * 100, 2)}%` }}
                      />
                    </div>
                    <span className="text-slate-500 w-12 text-right">{(score * 100).toFixed(0)}%</span>
                  </div>
                ))}
                {reviewResult.response && (
                  <p className="text-slate-300 mt-2">{reviewResult.response}</p>
                )}
              </div>
            ) : (
              <p className="text-slate-500">No problems detected.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
