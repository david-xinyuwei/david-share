'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

interface TaskResult {
  model: string
  sector: string
  occupation: string
  completeness: number
  accuracy: number
  professionalism: number
  clarity: number
  actionability: number
  overall: number
  latency: number
  response?: string
  judge_summary?: string
  judge_strengths?: string
  judge_weaknesses?: string
  human_score?: number | null
  notes?: string
}

interface EvalReasons {
  completeness: string
  accuracy: string
  professionalism: string
  clarity: string
  actionability: string
}

interface ResultsTableProps {
  results: TaskResult[]
  evalReasons: Map<number, EvalReasons>
  humanScores: Map<number, number>
  onHumanScoreChange: (index: number, score: number | null) => void
  readonly?: boolean
}

export function ResultsTable({ results, evalReasons, humanScores, onHumanScoreChange, readonly = false }: ResultsTableProps) {
  const [expandedRow, setExpandedRow] = useState<number | null>(null)
  
  const handleHumanScoreChange = (index: number, value: string) => {
    if (value === '' || value === '-') {
      onHumanScoreChange(index, null)
      return
    }
    const score = parseFloat(value)
    if (!isNaN(score) && score >= 0 && score <= 10) {
      onHumanScoreChange(index, score)
    }
  }
  
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-dark-border">
            <th className="text-left py-3 px-2 text-dark-muted font-medium">Model</th>
            <th className="text-left py-3 px-2 text-dark-muted font-medium">Sector</th>
            <th className="text-left py-3 px-2 text-dark-muted font-medium">Task</th>
            <th className="text-center py-3 px-2 text-dark-muted font-medium">Complete</th>
            <th className="text-center py-3 px-2 text-dark-muted font-medium">Accurate</th>
            <th className="text-center py-3 px-2 text-dark-muted font-medium">Professional</th>
            <th className="text-center py-3 px-2 text-dark-muted font-medium">Clear</th>
            <th className="text-center py-3 px-2 text-dark-muted font-medium">Actionable</th>
            <th className="text-center py-3 px-2 text-cyan-400 font-medium">Overall(AI)</th>
            <th className="text-center py-3 px-2 text-dark-muted font-medium">Latency</th>
            <th className="text-center py-3 px-2 text-purple-400 font-medium" title="Human score overrides AI overall">Overall(Human)</th>
            <th className="text-center py-3 px-2 text-dark-muted font-medium">Details</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result, idx) => (
            <>
              <tr 
                key={idx} 
                className="border-b border-dark-border/50 hover:bg-dark-card/50 transition-colors"
              >
                <td className="py-2 px-2 text-purple-400">{result.model}</td>
                <td className="py-2 px-2 text-dark-muted text-xs">{result.sector.slice(0, 15)}...</td>
                <td className="py-2 px-2 text-dark-text text-xs">{result.occupation.slice(0, 20)}...</td>
                <td className="py-2 px-2 text-center">{result.completeness}</td>
                <td className="py-2 px-2 text-center">{result.accuracy}</td>
                <td className="py-2 px-2 text-center">{result.professionalism}</td>
                <td className="py-2 px-2 text-center">{result.clarity}</td>
                <td className="py-2 px-2 text-center">{result.actionability}</td>
                <td className="py-2 px-2 text-center font-bold text-cyan-400">{result.overall}</td>
                <td className="py-2 px-2 text-center text-dark-muted">{result.latency}s</td>
                <td className="py-2 px-2 text-center">
                  <input
                    type="number"
                    min={0}
                    max={10}
                    step={0.1}
                    value={humanScores.get(idx) ?? ''}
                    onChange={(e) => handleHumanScoreChange(idx, e.target.value)}
                    disabled={readonly}
                    className={`w-14 px-2 py-1 bg-dark-bg border border-dark-border rounded text-center 
                      ${readonly ? 'text-dark-muted cursor-not-allowed' : 'text-purple-400'}
                      ${humanScores.has(idx) ? 'border-purple-500 bg-purple-900/20' : ''}`}
                    placeholder="-"
                  />
                </td>
                <td className="py-2 px-2 text-center">
                  <button
                    onClick={() => setExpandedRow(expandedRow === idx ? null : idx)}
                    className="p-1 hover:bg-dark-border rounded transition-colors"
                  >
                    {expandedRow === idx ? (
                      <ChevronUp className="w-4 h-4 text-cyan-400" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-dark-muted" />
                    )}
                  </button>
                </td>
              </tr>
              
              {/* Expanded details row */}
              {expandedRow === idx && (
                <tr className="bg-dark-bg/50">
                  <td colSpan={12} className="py-4 px-4">
                    <div className="space-y-3">
                      {/* Score reasons */}
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {evalReasons.get(idx) && Object.entries(evalReasons.get(idx)!).map(([key, reason]) => (
                          <div key={key} className="bg-dark-card p-3 rounded-lg">
                            <div className="text-xs text-dark-muted mb-1 capitalize">{key}</div>
                            <div className="text-sm text-dark-text">{reason || 'N/A'}</div>
                          </div>
                        ))}
                      </div>
                      
                      {/* Summary */}
                      {result.judge_summary && (
                        <div className="bg-dark-card p-3 rounded-lg">
                          <div className="text-xs text-dark-muted mb-1">📝 Summary</div>
                          <div className="text-sm text-dark-text">{result.judge_summary}</div>
                        </div>
                      )}
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {result.judge_strengths && (
                          <div className="bg-green-900/20 p-3 rounded-lg border border-green-800/50">
                            <div className="text-xs text-green-400 mb-1">💪 Strengths</div>
                            <div className="text-sm text-dark-text">{result.judge_strengths}</div>
                          </div>
                        )}
                        {result.judge_weaknesses && (
                          <div className="bg-red-900/20 p-3 rounded-lg border border-red-800/50">
                            <div className="text-xs text-red-400 mb-1">⚠️ Weaknesses</div>
                            <div className="text-sm text-dark-text">{result.judge_weaknesses}</div>
                          </div>
                        )}
                      </div>
                      
                      {/* Model response */}
                      {result.response && (
                        <div className="bg-dark-card p-3 rounded-lg">
                          <div className="text-xs text-dark-muted mb-1">📄 Model Response (Summary)</div>
                          <div className="text-sm text-dark-text/80 max-h-32 overflow-auto">
                            {result.response}
                          </div>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  )
}
