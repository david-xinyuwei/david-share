'use client'

import { CheckCircle, Circle, Loader2, UserCheck, BarChart3 } from 'lucide-react'

interface BenchmarkState {
  phase: 'idle' | 'phase1' | 'phase2' | 'phase3' | 'phase4'
  current: number
  total: number
  currentModel: string
  currentTask: string
}

interface ProgressPanelProps {
  state: BenchmarkState
  lang: {
    phase1: string
    phase2: string
    phase3: string
    phase4: string
  }
  humanScoreCount?: number
  onConfirmReview?: () => void
}

export function ProgressPanel({ state, lang, humanScoreCount = 0, onConfirmReview }: ProgressPanelProps) {
  const { phase, current, total, currentModel, currentTask } = state
  
  const progress = total > 0 ? (current / total) * 100 : 0
  
  const phases = [
    { id: 'phase1', label: lang.phase1.replace('Phase ', ''), icon: '🤖' },
    { id: 'phase2', label: lang.phase2.replace('Phase ', ''), icon: '🔍' },
    { id: 'phase3', label: lang.phase3.replace('Phase ', ''), icon: '👤' },
    { id: 'phase4', label: lang.phase4.replace('Phase ', ''), icon: '📊' },
  ]
  
  const getPhaseStatus = (phaseId: string) => {
    const phaseOrder = ['phase1', 'phase2', 'phase3', 'phase4']
    const currentIdx = phaseOrder.indexOf(phase)
    const targetIdx = phaseOrder.indexOf(phaseId)

    if (phase === 'idle') return 'pending'
    // Phase 3 & 4 are completion states - show checkmark, not spinner
    if (phase === 'phase3' && phaseId === 'phase3') return 'complete'
    if (phase === 'phase4' && (phaseId === 'phase3' || phaseId === 'phase4')) return 'complete'
    if (targetIdx < currentIdx) return 'complete'
    if (targetIdx === currentIdx) return 'active'
    return 'pending'
  }
  
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">📋 Progress</h3>
      
      {/* Phase indicator */}
      <div className="grid grid-cols-4 gap-1 mb-4">
        {phases.map((p, idx) => {
          const status = getPhaseStatus(p.id)
          return (
            <div key={p.id} className="flex flex-col items-center">
              <div className={`flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs w-full justify-center
                ${status === 'active' ? 'bg-cyan-900/50 text-cyan-400 ring-2 ring-cyan-500/50' : ''}
                ${status === 'complete' ? 'bg-green-900/50 text-green-400' : ''}
                ${status === 'pending' ? 'text-dark-muted bg-dark-bg/50' : ''}
              `}>
                {status === 'complete' && <CheckCircle className="w-3 h-3 flex-shrink-0" />}
                {status === 'active' && <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />}
                {status === 'pending' && <Circle className="w-3 h-3 flex-shrink-0" />}
                <span className="font-medium truncate">{p.icon} {p.label}</span>
              </div>
            </div>
          )
        })}
      </div>
      
      {/* Progress bar - Phase 1 & 2 */}
      {(phase === 'phase1' || phase === 'phase2') && (
        <>
          <div className="progress-bar mb-2">
            <div 
              className="progress-bar-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          
          <div className="flex justify-between text-sm">
            <span className="text-dark-muted">
              {current} / {total}
            </span>
            <span className="text-cyan-400 font-mono">
              {progress.toFixed(1)}%
            </span>
          </div>
          
          {/* Current task info */}
          {currentModel && (
            <div className="mt-3 p-3 bg-dark-bg rounded-lg text-sm">
              <div className="flex items-center gap-2">
                <span className="text-dark-muted">Model:</span>
                <span className="text-purple-400 font-medium">{currentModel}</span>
              </div>
              {currentTask && (
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-dark-muted">Task:</span>
                  <span className="text-cyan-400">{currentTask.slice(0, 40)}...</span>
                </div>
              )}
            </div>
          )}
        </>
      )}
      
      {/* Phase 3: Complete + Optional human review */}
      {phase === 'phase3' && (
        <div className="mt-3 space-y-3">
          {/* Complete notice */}
          <div className="p-3 bg-green-900/30 border border-green-500/50 rounded-lg">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <span className="text-green-300 font-medium">🎉 Complete! Charts generated, ready to export</span>
            </div>
          </div>
          
          {/* Optional human review */}
          <div className="p-3 bg-dark-bg/50 border border-dark-border rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-purple-400" />
                <span className="text-sm text-dark-muted">
                  Optional: Modify scores in table
                  {humanScoreCount > 0 && (
                    <span className="text-purple-400 font-medium"> (Modified {humanScoreCount})</span>
                  )}
                </span>
              </div>
              
              {humanScoreCount > 0 && (
                <button
                  onClick={onConfirmReview}
                  className="px-3 py-1.5 bg-gradient-to-r from-purple-500 to-pink-500 
                             hover:from-purple-600 hover:to-pink-600 
                             rounded-lg text-sm font-medium text-white flex items-center gap-1
                             transition-all hover:scale-105"
                >
                  <BarChart3 className="w-3 h-3" />
                  Regenerate Charts
                </button>
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* Phase 4: Final results with human corrections */}
      {phase === 'phase4' && (
        <div className="mt-3 p-4 bg-green-900/30 border border-green-500/50 rounded-lg">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-6 h-6 text-green-400" />
            <div>
              <div className="text-green-300 font-medium">🎉 Charts Updated!</div>
              <div className="text-sm text-dark-muted">
                Includes {humanScoreCount} human corrections
              </div>
            </div>
          </div>
        </div>
      )}
      
      {phase === 'idle' && (
        <div className="text-center text-dark-muted py-4">
          Waiting to start...
        </div>
      )}
    </div>
  )
}
