'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { 
  Play, Settings, Download,
  CheckCircle, Circle, Loader2, AlertCircle,
  ChevronDown, ChevronUp
} from 'lucide-react'
import { RadarChart } from '@/components/RadarChart'
import { BarChart } from '@/components/BarChart'
import { HeatMap } from '@/components/HeatMap'
import { ResultsTable } from '@/components/ResultsTable'
import { StreamLog } from '@/components/StreamLog'
import { ProgressPanel } from '@/components/ProgressPanel'

// 类型定义
interface SectorStats {
  [key: string]: number
}

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
  input_tokens?: number
  output_tokens?: number
  cached_tokens?: number
  response?: string
  judge_summary?: string
  judge_strengths?: string
  judge_weaknesses?: string
  human_score?: number | null
  notes?: string
}

// 模型定价 (per 1M tokens) - cached 是缓存命中的输入价格
const MODEL_PRICING: { [key: string]: { input: number; cached: number; output: number; context: number } } = {
  'grok-3': { input: 3.00, cached: 0.30, output: 15.00, context: 1000000 },
  'grok-3-mini': { input: 0.25, cached: 0.025, output: 1.27, context: 1000000 },
  'grok-4': { input: 3.00, cached: 0.30, output: 15.00, context: 200000 },
  'grok-4-fast-reasoning': { input: 0.20, cached: 0.02, output: 0.50, context: 200000 },
  'grok-4-fast-non-reasoning': { input: 0.20, cached: 0.02, output: 0.50, context: 200000 },
  'grok-code-fast-1': { input: 0.20, cached: 0.02, output: 1.50, context: 200000 },
  'gpt-5.1-chat-baseline': { input: 1.50, cached: 0.375, output: 6.00, context: 200000 },  // GPT-5.1 pricing
}

interface EvalReasons {
  completeness: string
  accuracy: string
  professionalism: string
  clarity: string
  actionability: string
}

interface BenchmarkState {
  phase: 'idle' | 'phase1' | 'phase2' | 'phase3' | 'phase4'
  current: number
  total: number
  currentModel: string
  currentTask: string
}

// UI Text (English only)
const L = {
  title: 'GDPVAL Grok Benchmark Tool',
  subtitle: 'AI Model Evaluation on Real-World Economically Valuable Tasks',
  selectSectors: 'Select Sectors',
  selectModels: 'Select Grok Models',
  tasksPerSector: 'Tasks per Sector',
  apiConfig: 'API Configuration',
  startBenchmark: '🚀 Start Benchmark',
  running: 'Running...',
  stop: '⏹ Stop',
  phase1: 'Phase 1: Model Testing',
  phase2: 'Phase 2: AI Evaluation',
  phase3: 'Phase 3: Human Re-check',
  phase4: 'Phase 4: Complete',
  streamLog: 'Real-time Log',
  results: 'Results',
  radarChart: 'Capability Radar',
  barChart: 'Model Ranking',
  heatMap: 'Sector × Model Heatmap',
  exportJson: 'Export JSON',
  exportExcel: 'Export Excel',
  exportReport: '📊 Export Report',
  version: 'Developed by Xinyuwei | V0.4',
  regenerateCharts: '🔄 Regenerate Charts',
  changes: 'changes',
  correctionsApplied: '✅ Corrections Applied',
  tasks: 'tasks',
  keyInsights: '💡 Key Insights',
  costLatency: '💰 Cost & Latency',
  noInsightsYet: 'Run benchmark to see insights',
  bestModel: 'Best Overall',
  fastestModel: 'Fastest',
  cheapestModel: 'Most Cost-Effective',
  totalCost: 'Total Cost',
  avgLatency: 'Avg Latency',
}

const GROK_MODELS = [
  'grok-3',
  'grok-3-mini',
  'grok-4',
  'grok-4-fast-reasoning',
  'grok-4-fast-non-reasoning',
  'grok-code-fast-1',
  'gpt-5.1-chat-baseline'
]

export default function Home() {
  // Data state
  const [sectorStats, setSectorStats] = useState<SectorStats>({})
  const [selectedSectors, setSelectedSectors] = useState<string[]>(['Manufacturing', 'Finance and Insurance'])
  const [selectedModels, setSelectedModels] = useState<string[]>(['grok-3-mini', 'grok-4-fast-non-reasoning'])
  const [tasksPerSector, setTasksPerSector] = useState(2)
  
  // API 配置 - 默认值 (请在界面中填写实际的 API Key)
  const [showApiConfig, setShowApiConfig] = useState(false)
  const [grokEndpoint, setGrokEndpoint] = useState('')
  const [grokApiKey, setGrokApiKey] = useState('')
  const [judgeEndpoint, setJudgeEndpoint] = useState('')
  const [judgeApiKey, setJudgeApiKey] = useState('')
  const [judgeModel, setJudgeModel] = useState('gpt-5.2-chat')
  const [judgeApiVersion, setJudgeApiVersion] = useState('2025-04-01-preview')
  
  // 评测状态
  const [benchmarkState, setBenchmarkState] = useState<BenchmarkState>({
    phase: 'idle',
    current: 0,
    total: 0,
    currentModel: '',
    currentTask: ''
  })
  
  // 结果
  const [streamContent, setStreamContent] = useState('')
  const [results, setResults] = useState<TaskResult[]>([])
  const [evalReasons, setEvalReasons] = useState<Map<number, EvalReasons>>(new Map())
  
  // 人工评分
  const [humanScores, setHumanScores] = useState<Map<number, number>>(new Map())
  // 用于图表的数据 (可能Including人工修正)
  const [chartData, setChartData] = useState<TaskResult[]>([])
  
  const wsRef = useRef<WebSocket | null>(null)

  // Stop benchmark
  const stopBenchmark = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setBenchmarkState(prev => ({
      ...prev,
      phase: 'idle',
      current: 0,
      total: 0
    }))
    setStreamContent(prev => prev + '\n\n⏹ Benchmark stopped by user.\n')
  }, [])
  
  // 获取数据集信息
  useEffect(() => {
    fetch('/api/info')
      .then(res => res.json())
      .then(data => {
        setSectorStats(data.sectors || {})
      })
      .catch(err => {
        console.error('Failed to load info:', err)
        // 使用默认数据
        setSectorStats({
          'Professional, Scientific, and Technical Services': 50,
          'Manufacturing': 30,
          'Finance and Insurance': 30,
          'Health Care and Social Assistance': 30,
          'Retail Trade': 20,
          'Government': 20,
          'Information': 15,
          'Real Estate and Rental and Leasing': 15,
          'Wholesale Trade': 10
        })
      })
  }, [])
  
  // 开始评测
  const startBenchmark = useCallback(() => {
    if (selectedSectors.length === 0 || selectedModels.length === 0) {
      alert('Please select at least one sector and one model')
      return
    }
    
    if (!grokApiKey || !judgeApiKey) {
      alert('Please enter API Key')
      setShowApiConfig(true)
      return
    }
    
    // 重置状态
    setStreamContent('')
    setResults([])
    setEvalReasons(new Map())
    setHumanScores(new Map())
    setChartData([])
    setBenchmarkState({
      phase: 'phase1',
      current: 0,
      total: selectedSectors.length * selectedModels.length * tasksPerSector,
      currentModel: '',
      currentTask: ''
    })
    
    // 建立 WebSocket 连接 - 自动检测主机名
    const wsHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost'
    const ws = new WebSocket(`ws://${wsHost}:8000/ws/benchmark`)
    wsRef.current = ws
    
    ws.onopen = () => {
      // 发送配置
      ws.send(JSON.stringify({
        sectors: selectedSectors,
        models: selectedModels,
        tasks_per_sector: tasksPerSector,
        grok_endpoint: grokEndpoint,
        grok_api_key: grokApiKey,
        judge_endpoint: judgeEndpoint,
        judge_api_key: judgeApiKey,
        judge_model: judgeModel,
        judge_api_version: judgeApiVersion
      }))
    }
    
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      
      switch (msg.type) {
        case 'start':
          setBenchmarkState(prev => ({ ...prev, total: msg.total }))
          setStreamContent(prev => prev + `\n🚀 Starting benchmark: ${msg.total} tasks\n`)
          break
          
        case 'phase1_progress':
          setBenchmarkState(prev => ({
            ...prev,
            phase: 'phase1',
            current: msg.current,
            total: msg.total,
            currentModel: msg.model,
            currentTask: msg.occupation
          }))
          break
          
        case 'stream_start':
          setStreamContent(prev => 
            prev + `\n${'─'.repeat(50)}\n📍 ${msg.model} | ${msg.task}\n${'─'.repeat(50)}\n`
          )
          break
          
        case 'stream':
          setStreamContent(prev => prev + msg.content)
          break
          
        case 'phase1_complete':
          setStreamContent(prev => prev + `\n✅ Done (${msg.latency}s)\n`)
          break
          
        case 'phase2_start':
          setBenchmarkState(prev => ({
            ...prev,
            phase: 'phase2',
            current: 0,
            total: msg.total
          }))
          setStreamContent(prev => prev + `\n\n${'═'.repeat(50)}\n🔍 Phase 2: GPT-5.2 Evaluation\n${'═'.repeat(50)}\n`)
          break
          
        case 'phase2_progress':
          setBenchmarkState(prev => ({
            ...prev,
            current: msg.current,
            currentModel: msg.model,
            currentTask: msg.occupation
          }))
          break
          
        case 'phase2_result':
          setResults(prev => [...prev, msg.result])
          setChartData(prev => [...prev, msg.result])  // 实时更新图表
          setEvalReasons(prev => new Map(prev).set(msg.index, msg.reasons))
          setStreamContent(prev => 
            prev + `\n📊 ${msg.result.model} | ${msg.result.occupation}: ${msg.result.overall}/10\n`
          )
          break
          
        case 'phase2_error':
          setStreamContent(prev => prev + `\n❌ Evaluation failed: ${msg.error}\n`)
          break
          
        case 'complete':
          setBenchmarkState(prev => ({ ...prev, phase: 'phase3' }))  // 进入人工复核阶段（可选）
          setStreamContent(prev => 
            prev + `\n\n${'═'.repeat(50)}\n🎉 Benchmark complete! Total ${msg.total} results\n📊 Charts generated. Ready to export.\n👤 To adjust scores, edit the table below and click "Regenerate Charts"\n${'═'.repeat(50)}\n`
          )
          // 初始化图表数据为原始结果
          setChartData(msg.results || [])
          ws.close()
          break
          
        case 'error':
          setStreamContent(prev => prev + `\n❌ Error: ${msg.message}\n`)
          break
      }
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setStreamContent(prev => prev + '\n❌ WebSocket 连接错误\n')
      setBenchmarkState(prev => ({ ...prev, phase: 'idle' }))
    }
    
    ws.onclose = () => {
      console.log('WebSocket closed')
    }
  }, [selectedSectors, selectedModels, tasksPerSector, grokEndpoint, grokApiKey, judgeEndpoint, judgeApiKey, judgeModel])
  
  // 人工评分修改
  const handleHumanScoreChange = useCallback((index: number, score: number | null) => {
    setHumanScores(prev => {
      const newMap = new Map(prev)
      if (score === null) {
        newMap.delete(index)
      } else {
        newMap.set(index, score)
      }
      return newMap
    })
  }, [])
  
  // 重新生成图表 (使用人工评分覆盖)
  const regenerateCharts = useCallback(() => {
    const newChartData = results.map((result, idx) => {
      const humanScore = humanScores.get(idx)
      if (humanScore !== undefined) {
        return { ...result, overall: humanScore }
      }
      return result
    })
    setChartData(newChartData)
    setStreamContent(prev => prev + `\n🔄 Charts updated (${humanScores.size} human scores applied)\n`)
  }, [results, humanScores])
  
  // 确认人工复核完成，进入阶段4
  const confirmHumanReview = useCallback(() => {
    // 应用人工评分生成最终图表数据
    const finalChartData = results.map((result, idx) => {
      const humanScore = humanScores.get(idx)
      if (humanScore !== undefined) {
        return { ...result, overall: humanScore }
      }
      return result
    })
    setChartData(finalChartData)
    
    // 进入阶段4
    setBenchmarkState(prev => ({ ...prev, phase: 'phase4' }))
    setStreamContent(prev => 
      prev + `\n\n${'═'.repeat(50)}\n🎉 Final results generated!\n📊 Including ${humanScores.size} human corrections\n${'═'.repeat(50)}\n`
    )
  }, [results, humanScores])
  
  // 切换行业选择
  const toggleSector = (sector: string) => {
    setSelectedSectors(prev => 
      prev.includes(sector) 
        ? prev.filter(s => s !== sector)
        : [...prev, sector]
    )
  }
  
  // 切换模型选择
  const toggleModel = (model: string) => {
    setSelectedModels(prev =>
      prev.includes(model)
        ? prev.filter(m => m !== model)
        : [...prev, model]
    )
  }
  
  // 计算最大任务数
  const maxTasks = Math.max(
    1,
    Math.min(
      ...selectedSectors.map(s => sectorStats[s] || 10)
    )
  )
  
  const isRunning = benchmarkState.phase === 'phase1' || benchmarkState.phase === 'phase2'
  
  // 导出 JSON 下载
  const exportJson = () => {
    if (results.length === 0) return
    
    const exportData = {
      timestamp: new Date().toISOString(),
      config: {
        sectors: selectedSectors,
        models: selectedModels,
        tasks_per_sector: tasksPerSector
      },
      results: results,
      eval_reasons: Object.fromEntries(evalReasons)
    }
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `gdpval_results_${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }
  
  // 导出 HTML 报告
  const exportReport = () => {
    if (results.length === 0) return
    
    // 计算模型汇总数据
    const modelStats: { [key: string]: { scores: number[], dims: { [k: string]: number[] } } } = {}
    chartData.forEach(r => {
      if (!modelStats[r.model]) {
        modelStats[r.model] = { scores: [], dims: { completeness: [], accuracy: [], professionalism: [], clarity: [], actionability: [] } }
      }
      modelStats[r.model].scores.push(r.overall)
      modelStats[r.model].dims.completeness.push(r.completeness)
      modelStats[r.model].dims.accuracy.push(r.accuracy)
      modelStats[r.model].dims.professionalism.push(r.professionalism)
      modelStats[r.model].dims.clarity.push(r.clarity)
      modelStats[r.model].dims.actionability.push(r.actionability)
    })
    
    const modelRanking = Object.entries(modelStats).map(([model, data]) => ({
      model,
      overall: (data.scores.reduce((a, b) => a + b, 0) / data.scores.length).toFixed(2),
      completeness: (data.dims.completeness.reduce((a, b) => a + b, 0) / data.dims.completeness.length).toFixed(2),
      accuracy: (data.dims.accuracy.reduce((a, b) => a + b, 0) / data.dims.accuracy.length).toFixed(2),
      professionalism: (data.dims.professionalism.reduce((a, b) => a + b, 0) / data.dims.professionalism.length).toFixed(2),
      clarity: (data.dims.clarity.reduce((a, b) => a + b, 0) / data.dims.clarity.length).toFixed(2),
      actionability: (data.dims.actionability.reduce((a, b) => a + b, 0) / data.dims.actionability.length).toFixed(2),
      count: data.scores.length
    })).sort((a, b) => parseFloat(b.overall) - parseFloat(a.overall))
    
    // 计算行业×模型矩阵
    const sectors = [...new Set(chartData.map(r => r.sector))]
    const models = [...new Set(chartData.map(r => r.model))]
    const heatmapData: { [sector: string]: { [model: string]: number } } = {}
    sectors.forEach(s => { heatmapData[s] = {} })
    chartData.forEach(r => {
      if (!heatmapData[r.sector][r.model]) heatmapData[r.sector][r.model] = 0
      heatmapData[r.sector][r.model] = (heatmapData[r.sector][r.model] + r.overall) / 2 || r.overall
    })
    
    const isPhase4 = benchmarkState.phase === 'phase4'
    const reportTitle = isPhase4 ? 'GDPVAL Benchmark Report (Final)' : 'GDPVAL Benchmark Report'
    
    const html = `<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${reportTitle}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 40px; line-height: 1.6; }
    .container { max-width: 1200px; margin: 0 auto; }
    h1 { text-align: center; font-size: 2.5em; margin-bottom: 10px; background: linear-gradient(135deg, #00d4ff, #00ff88); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .subtitle { text-align: center; color: #8b949e; margin-bottom: 30px; }
    .meta { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 30px; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
    .meta-item { text-align: center; }
    .meta-label { color: #8b949e; font-size: 0.9em; }
    .meta-value { font-size: 1.5em; color: #58a6ff; font-weight: bold; }
    .section { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 30px; }
    .section-title { font-size: 1.3em; margin-bottom: 20px; color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
    .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 30px; }
    .chart-container { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }
    .chart-title { text-align: center; margin-bottom: 15px; color: #c9d1d9; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
    th, td { padding: 12px 8px; text-align: left; border-bottom: 1px solid #30363d; }
    th { background: #21262d; color: #8b949e; font-weight: 500; }
    tr:hover { background: #21262d; }
    .score { text-align: center; font-weight: bold; }
    .score-high { color: #3fb950; }
    .score-mid { color: #d29922; }
    .score-low { color: #f85149; }
    .ranking-bar { height: 24px; border-radius: 4px; background: linear-gradient(90deg, #00d4ff, #00ff88); }
    .heatmap { display: grid; gap: 2px; }
    .heatmap-cell { padding: 8px; text-align: center; border-radius: 4px; font-size: 0.85em; }
    .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8em; margin-left: 10px; }
    .badge-final { background: #238636; color: white; }
    .badge-ai { background: #1f6feb; color: white; }
    @media print { body { background: white; color: black; } .section, .chart-container, .meta { background: #f6f8fa; border-color: #d0d7de; } th { background: #f6f8fa; } }
  </style>
</head>
<body>
  <div class="container">
    <h1>🎯 ${reportTitle}</h1>
    <p class="subtitle">AI Model Benchmark Report on Real Economic Value Tasks ${isPhase4 ? '<span class="badge badge-final">Human Reviewed</span>' : '<span class="badge badge-ai">AI Evaluated</span>'}</p>
    
    <div class="meta">
      <div class="meta-item"><div class="meta-label">Date</div><div class="meta-value">${new Date().toLocaleDateString('en-US')}</div></div>
      <div class="meta-item"><div class="meta-label">Models</div><div class="meta-value">${models.length}</div></div>
      <div class="meta-item"><div class="meta-label">Sectors</div><div class="meta-value">${sectors.length}</div></div>
      <div class="meta-item"><div class="meta-label">Tasks</div><div class="meta-value">${chartData.length}</div></div>
      ${isPhase4 ? `<div class="meta-item"><div class="meta-label">人工修正</div><div class="meta-value">${humanScores.size}</div></div>` : ''}
    </div>
    
    <div class="charts">
      <div class="chart-container">
        <h3 class="chart-title">📊 Model Ranking (Overall)</h3>
        <canvas id="barChart"></canvas>
      </div>
      <div class="chart-container">
        <h3 class="chart-title">🎯 能力雷达图</h3>
        <canvas id="radarChart"></canvas>
      </div>
    </div>
    
    <div class="section">
      <h2 class="section-title">📈 Model Performance Summary</h2>
      <table>
        <thead>
          <tr>
            <th>排名</th>
            <th>Model</th>
            <th class="score">综合</th>
            <th class="score">Comp</th>
            <th class="score">Accur</th>
            <th class="score">Prof</th>
            <th class="score">Clear</th>
            <th class="score">Action</th>
            <th class="score">任务数</th>
          </tr>
        </thead>
        <tbody>
          ${modelRanking.map((m, i) => `
          <tr>
            <td>${i + 1}</td>
            <td><strong>${m.model}</strong></td>
            <td class="score ${parseFloat(m.overall) >= 8 ? 'score-high' : parseFloat(m.overall) >= 6 ? 'score-mid' : 'score-low'}">${m.overall}</td>
            <td class="score">${m.completeness}</td>
            <td class="score">${m.accuracy}</td>
            <td class="score">${m.professionalism}</td>
            <td class="score">${m.clarity}</td>
            <td class="score">${m.actionability}</td>
            <td class="score">${m.count}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
    
    <div class="section">
      <h2 class="section-title">🗺️ Sector × Model Heatmap</h2>
      <table>
        <thead>
          <tr>
            <th>Sector</th>
            ${models.map(m => `<th class="score">${m.replace('grok-', '')}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${sectors.map(s => `
          <tr>
            <td>${s}</td>
            ${models.map(m => {
              const score = heatmapData[s]?.[m]
              const color = score ? (score >= 8 ? '#238636' : score >= 6 ? '#9e6a03' : '#da3633') : '#30363d'
              return `<td class="score" style="background: ${color}40; color: ${score ? '#fff' : '#8b949e'}">${score ? score.toFixed(1) : '-'}</td>`
            }).join('')}
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
    
    <div class="section">
      <h2 class="section-title">📋 Detailed Results</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Model</th>
            <th>Sector</th>
            <th>任务</th>
            <th class="score">Comp</th>
            <th class="score">Accur</th>
            <th class="score">Prof</th>
            <th class="score">Clear</th>
            <th class="score">Action</th>
            <th class="score">综合</th>
            <th class="score">耗时</th>
          </tr>
        </thead>
        <tbody>
          ${chartData.map((r, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${r.model}</td>
            <td>${r.sector}</td>
            <td>${r.occupation.substring(0, 30)}${r.occupation.length > 30 ? '...' : ''}</td>
            <td class="score">${r.completeness}</td>
            <td class="score">${r.accuracy}</td>
            <td class="score">${r.professionalism}</td>
            <td class="score">${r.clarity}</td>
            <td class="score">${r.actionability}</td>
            <td class="score ${r.overall >= 8 ? 'score-high' : r.overall >= 6 ? 'score-mid' : 'score-low'}">${r.overall}</td>
            <td class="score">${r.latency.toFixed(1)}s</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
    
    <footer style="text-align: center; color: #8b949e; margin-top: 40px; padding-top: 20px; border-top: 1px solid #30363d;">
      Generated by GDPVAL Benchmark Tool | Developed by Xinyuwei | ${new Date().toLocaleString('zh-CN')}
    </footer>
  </div>
  
  <script>
    // 柱状图
    const barCtx = document.getElementById('barChart').getContext('2d');
    new Chart(barCtx, {
      type: 'bar',
      data: {
        labels: ${JSON.stringify(modelRanking.map(m => m.model.replace('grok-', '')))},
        datasets: [{
          label: '综合分',
          data: ${JSON.stringify(modelRanking.map(m => parseFloat(m.overall)))},
          backgroundColor: 'rgba(0, 212, 255, 0.7)',
          borderColor: 'rgba(0, 212, 255, 1)',
          borderWidth: 1
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        scales: { x: { min: 0, max: 10, grid: { color: '#30363d' } }, y: { grid: { color: '#30363d' } } },
        plugins: { legend: { display: false } }
      }
    });
    
    // 雷达图
    const radarCtx = document.getElementById('radarChart').getContext('2d');
    const radarColors = ['#00d4ff', '#00ff88', '#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff'];
    new Chart(radarCtx, {
      type: 'radar',
      data: {
        labels: ['Complete', 'Accurate', 'Professional', 'Clarity', 'Actionable'],
        datasets: ${JSON.stringify(modelRanking.map((m, i) => ({
          label: m.model.replace('grok-', ''),
          data: [parseFloat(m.completeness), parseFloat(m.accuracy), parseFloat(m.professionalism), parseFloat(m.clarity), parseFloat(m.actionability)],
          borderColor: `radarColors[${i % 6}]`,
          backgroundColor: `radarColors[${i % 6}]`.replace(')', ', 0.1)').replace('rgb', 'rgba'),
          borderWidth: 2,
          pointRadius: 3
        })))}.map((d, i) => ({...d, borderColor: radarColors[i % 6], backgroundColor: radarColors[i % 6] + '20'}))
      },
      options: {
        responsive: true,
        scales: { r: { min: 0, max: 10, grid: { color: '#30363d' }, angleLines: { color: '#30363d' }, pointLabels: { color: '#c9d1d9' } } },
        plugins: { legend: { position: 'bottom', labels: { color: '#c9d1d9' } } }
      }
    });
  </script>
</body>
</html>`
    
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `gdpval_report_${new Date().toISOString().slice(0, 10)}${isPhase4 ? '_final' : ''}.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }
  
  // 导出 Excel (CSV) 下载
  const exportExcel = () => {
    if (results.length === 0) return
    
    // CSV 头部
    const headers = [
      'Model', 'Sector', 'Occupation', 
      'Completeness', 'Accuracy', 'Professionalism', 'Clarity', 'Actionability',
      'Overall', 'Latency(s)', 'Human Score', 'Notes'
    ]
    
    // CSV 数据行
    const rows = results.map(r => [
      r.model,
      r.sector,
      `"${r.occupation.replace(/"/g, '""')}"`,  // 转义引号
      r.completeness,
      r.accuracy,
      r.professionalism,
      r.clarity,
      r.actionability,
      r.overall,
      r.latency.toFixed(2),
      r.human_score ?? '',
      r.notes ? `"${r.notes.replace(/"/g, '""')}"` : ''
    ])
    
    // 添加 BOM 以支持中文
    const BOM = '\uFEFF'
    const csv = BOM + [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `gdpval_results_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }
  
  return (
    <main className="min-h-screen p-6">
      {/* Header */}
      <header className="text-center mb-8">
        <h1 className="text-4xl font-bold neon-title mb-2">
          🎯 {L.title}
        </h1>
        <p className="text-dark-muted">{L.subtitle}</p>
      </header>
      
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧配置面板 */}
        <div className="lg:col-span-1 space-y-4">
          {/* 行业选择 */}
          <div className="card">
            <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
              📁 {L.selectSectors}
            </h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(sectorStats).map(([sector, count]) => (
                <button
                  key={sector}
                  onClick={() => toggleSector(sector)}
                  disabled={isRunning}
                  className={`px-3 py-1.5 text-sm rounded-full border transition-all
                    ${selectedSectors.includes(sector)
                      ? 'bg-cyan-600 border-cyan-500 text-white'
                      : 'bg-dark-bg border-dark-border text-dark-muted hover:border-cyan-500'
                    } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {sector} ({count})
                </button>
              ))}
            </div>
          </div>
          
          {/* 模型选择 */}
          <div className="card">
            <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
              🤖 {L.selectModels}
            </h2>
            <div className="flex flex-wrap gap-2">
              {GROK_MODELS.map(model => (
                <button
                  key={model}
                  onClick={() => toggleModel(model)}
                  disabled={isRunning}
                  className={`px-3 py-1.5 text-sm rounded-full border transition-all
                    ${selectedModels.includes(model)
                      ? 'bg-purple-600 border-purple-500 text-white'
                      : 'bg-dark-bg border-dark-border text-dark-muted hover:border-purple-500'
                    } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {model}
                </button>
              ))}
            </div>
          </div>
          
          {/* 任务数滑块 */}
          <div className="card">
            <h2 className="text-lg font-semibold mb-3">📊 {L.tasksPerSector}</h2>
            <input
              type="range"
              min={1}
              max={maxTasks}
              value={Math.min(tasksPerSector, maxTasks)}
              onChange={(e) => setTasksPerSector(Number(e.target.value))}
              disabled={isRunning}
              className="w-full accent-cyan-500"
            />
            <div className="flex justify-between text-sm text-dark-muted mt-1">
              <span>1</span>
              <span className="text-cyan-400 font-bold">{Math.min(tasksPerSector, maxTasks)}</span>
              <span>{maxTasks}</span>
            </div>
          </div>
          
          {/* API 配置 */}
          <div className="card">
            <button
              onClick={() => setShowApiConfig(!showApiConfig)}
              className="w-full flex items-center justify-between text-lg font-semibold"
            >
              <span className="flex items-center gap-2">
                <Settings className="w-5 h-5" />
                {L.apiConfig}
              </span>
              {showApiConfig ? <ChevronUp /> : <ChevronDown />}
            </button>
            
            {showApiConfig && (
              <div className="mt-4 space-y-3">
                <div>
                  <label className="text-sm text-dark-muted">Grok Endpoint</label>
                  <input
                    type="text"
                    value={grokEndpoint}
                    onChange={(e) => setGrokEndpoint(e.target.value)}
                    className="w-full mt-1 px-3 py-2 bg-dark-bg border border-dark-border rounded-lg"
                  />
                </div>
                <div>
                  <label className="text-sm text-dark-muted">Grok API Key</label>
                  <input
                    type="password"
                    value={grokApiKey}
                    onChange={(e) => setGrokApiKey(e.target.value)}
                    className="w-full mt-1 px-3 py-2 bg-dark-bg border border-dark-border rounded-lg"
                  />
                </div>
                <div>
                  <label className="text-sm text-dark-muted">Judge Endpoint (Azure OpenAI)</label>
                  <input
                    type="text"
                    value={judgeEndpoint}
                    onChange={(e) => setJudgeEndpoint(e.target.value)}
                    className="w-full mt-1 px-3 py-2 bg-dark-bg border border-dark-border rounded-lg"
                  />
                </div>
                <div>
                  <label className="text-sm text-dark-muted">Judge API Key</label>
                  <input
                    type="password"
                    value={judgeApiKey}
                    onChange={(e) => setJudgeApiKey(e.target.value)}
                    className="w-full mt-1 px-3 py-2 bg-dark-bg border border-dark-border rounded-lg"
                  />
                </div>
                <div>
                  <label className="text-sm text-dark-muted">Judge Model</label>
                  <input
                    type="text"
                    value={judgeModel}
                    onChange={(e) => setJudgeModel(e.target.value)}
                    className="w-full mt-1 px-3 py-2 bg-dark-bg border border-dark-border rounded-lg"
                  />
                </div>
              </div>
            )}
          </div>
          
          {/* Start/Stop buttons */}
          <div className="flex gap-3">
            <button
              onClick={startBenchmark}
              disabled={isRunning}
              className={`flex-1 py-4 rounded-lg font-bold text-lg transition-all
                ${isRunning
                  ? 'bg-gray-600 cursor-not-allowed'
                  : 'bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600'
                }`}
            >
              {isRunning ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  {L.running}
                </span>
              ) : (
                L.startBenchmark
              )}
            </button>
            <button
              onClick={stopBenchmark}
              disabled={!isRunning}
              className={`px-6 py-4 rounded-lg font-bold text-lg transition-all
                ${isRunning
                  ? 'bg-red-600 hover:bg-red-700'
                  : 'bg-gray-700 cursor-not-allowed opacity-50'
                }`}
            >
              {L.stop}
            </button>
          </div>
          
          {/* Key Insights Panel */}
          <div className="card">
            <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
              {L.keyInsights}
            </h2>
            {chartData.length === 0 ? (
              <p className="text-dark-muted text-sm">{L.noInsightsYet}</p>
            ) : (() => {
              // 计算各模型统计
              const modelStats: { [key: string]: { scores: number[], latencies: number[], inputTokens: number, outputTokens: number } } = {}
              chartData.forEach(r => {
                if (!modelStats[r.model]) {
                  modelStats[r.model] = { scores: [], latencies: [], inputTokens: 0, outputTokens: 0 }
                }
                modelStats[r.model].scores.push(r.overall)
                modelStats[r.model].latencies.push(r.latency || 0)
                modelStats[r.model].inputTokens += r.input_tokens || 1000
                modelStats[r.model].outputTokens += r.output_tokens || 500
              })
              
              const modelRanks = Object.entries(modelStats).map(([model, data]) => ({
                model,
                avgScore: data.scores.reduce((a, b) => a + b, 0) / data.scores.length,
                avgLatency: data.latencies.reduce((a, b) => a + b, 0) / data.latencies.length,
                inputTokens: data.inputTokens,
                outputTokens: data.outputTokens,
                cost: (data.inputTokens / 1000000) * (MODEL_PRICING[model]?.input || 1) + 
                      (data.outputTokens / 1000000) * (MODEL_PRICING[model]?.output || 1)
              }))
              
              const bestModel = [...modelRanks].sort((a, b) => b.avgScore - a.avgScore)[0]
              const fastestModel = [...modelRanks].sort((a, b) => a.avgLatency - b.avgLatency)[0]
              const cheapestModel = [...modelRanks].sort((a, b) => a.cost - b.cost)[0]
              
              // 检查 Grok 是否在某些方面领先
              const grokWins: string[] = []
              if (bestModel?.model.startsWith('grok')) grokWins.push('Best Score')
              if (fastestModel?.model.startsWith('grok')) grokWins.push('Fastest')
              if (cheapestModel?.model.startsWith('grok')) grokWins.push('Cheapest')
              
              return (
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between items-center p-2 bg-green-900/30 rounded">
                    <span className="text-green-400">🏆 {L.bestModel}</span>
                    <span className="font-bold text-green-300">{bestModel?.model} ({bestModel?.avgScore.toFixed(1)})</span>
                  </div>
                  <div className="flex justify-between items-center p-2 bg-blue-900/30 rounded">
                    <span className="text-blue-400">⚡ {L.fastestModel}</span>
                    <span className="font-bold text-blue-300">{fastestModel?.model} ({fastestModel?.avgLatency.toFixed(1)}s)</span>
                  </div>
                  <div className="flex justify-between items-center p-2 bg-yellow-900/30 rounded">
                    <span className="text-yellow-400">💵 {L.cheapestModel}</span>
                    <span className="font-bold text-yellow-300">{cheapestModel?.model} (${cheapestModel?.cost.toFixed(4)})</span>
                  </div>
                  {grokWins.length > 0 && (
                    <div className="mt-2 p-2 bg-purple-900/30 rounded border border-purple-500">
                      <span className="text-purple-400">✨ Grok Advantages: </span>
                      <span className="text-purple-300 font-bold">{grokWins.join(', ')}</span>
                    </div>
                  )}
                </div>
              )
            })()}
          </div>
          
          {/* Cost & Latency Panel */}
          <div className="card">
            <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
              {L.costLatency}
            </h2>
            {chartData.length === 0 ? (
              <p className="text-dark-muted text-sm">{L.noInsightsYet}</p>
            ) : (() => {
              // 按模型汇总 (包含 cached tokens)
              const modelCosts: { [key: string]: { inputTokens: number, outputTokens: number, cachedTokens: number, latencies: number[], count: number } } = {}
              chartData.forEach(r => {
                if (!modelCosts[r.model]) {
                  modelCosts[r.model] = { inputTokens: 0, outputTokens: 0, cachedTokens: 0, latencies: [], count: 0 }
                }
                modelCosts[r.model].inputTokens += r.input_tokens || 1000
                modelCosts[r.model].outputTokens += r.output_tokens || 500
                modelCosts[r.model].cachedTokens += r.cached_tokens || 0
                modelCosts[r.model].latencies.push(r.latency || 0)
                modelCosts[r.model].count++
              })
              
              return (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-dark-border">
                        <th className="text-left py-2 px-1">Model</th>
                        <th className="text-right py-2 px-1">Input</th>
                        <th className="text-right py-2 px-1">Cached</th>
                        <th className="text-right py-2 px-1">Output</th>
                        <th className="text-right py-2 px-1">Cost</th>
                        <th className="text-right py-2 px-1">Latency</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(modelCosts).map(([model, data]) => {
                        const pricing = MODEL_PRICING[model] || { input: 1, cached: 0.1, output: 1 }
                        // 非缓存 input = total input - cached
                        const uncachedInput = data.inputTokens - data.cachedTokens
                        const inputCost = (uncachedInput / 1000000) * pricing.input
                        const cachedCost = (data.cachedTokens / 1000000) * pricing.cached
                        const outputCost = (data.outputTokens / 1000000) * pricing.output
                        const totalCost = inputCost + cachedCost + outputCost
                        const avgLatency = data.latencies.reduce((a, b) => a + b, 0) / data.latencies.length
                        
                        return (
                          <tr key={model} className="border-b border-dark-border/50 hover:bg-dark-bg">
                            <td className="py-2 px-1 font-medium truncate max-w-[100px]" title={model}>
                              {model.replace('grok-', '').replace('-baseline', '')}
                            </td>
                            <td className="text-right py-2 px-1 text-dark-muted">
                              {(data.inputTokens / 1000).toFixed(1)}K
                            </td>
                            <td className="text-right py-2 px-1 text-cyan-400">
                              {data.cachedTokens > 0 ? `${(data.cachedTokens / 1000).toFixed(1)}K` : '-'}
                            </td>
                            <td className="text-right py-2 px-1 text-dark-muted">
                              {(data.outputTokens / 1000).toFixed(1)}K
                            </td>
                            <td className="text-right py-2 px-1 text-green-400 font-mono">
                              ${totalCost.toFixed(4)}
                            </td>
                            <td className="text-right py-2 px-1 text-blue-400">
                              {avgLatency.toFixed(1)}s
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                    <tfoot>
                      <tr className="border-t border-dark-border">
                        <td className="py-2 px-1 font-bold">Total</td>
                        <td className="text-right py-2 px-1 text-dark-muted">
                          {(Object.values(modelCosts).reduce((sum, d) => sum + d.inputTokens, 0) / 1000).toFixed(1)}K
                        </td>
                        <td className="text-right py-2 px-1 text-cyan-400">
                          {(() => {
                            const totalCached = Object.values(modelCosts).reduce((sum, d) => sum + d.cachedTokens, 0)
                            return totalCached > 0 ? `${(totalCached / 1000).toFixed(1)}K` : '-'
                          })()}
                        </td>
                        <td className="text-right py-2 px-1 text-dark-muted">
                          {(Object.values(modelCosts).reduce((sum, d) => sum + d.outputTokens, 0) / 1000).toFixed(1)}K
                        </td>
                        <td className="text-right py-2 px-1 text-green-400 font-bold">
                          ${Object.entries(modelCosts).reduce((sum, [model, data]) => {
                            const pricing = MODEL_PRICING[model] || { input: 1, cached: 0.1, output: 1 }
                            const uncachedInput = data.inputTokens - data.cachedTokens
                            return sum + (uncachedInput / 1000000) * pricing.input + (data.cachedTokens / 1000000) * pricing.cached + (data.outputTokens / 1000000) * pricing.output
                          }, 0).toFixed(4)}
                        </td>
                        <td className="text-right py-2 px-1 text-blue-400">-</td>
                      </tr>
                    </tfoot>
                  </table>
                  <div className="mt-2 text-xs text-dark-muted">
                    💡 Pricing ($/1M): grok-4-fast $0.20/$0.50 | grok-3-mini $0.25/$1.27 | gpt-5.2 $1.75(cached $0.44)/$14.00
                  </div>
                </div>
              )
            })()}
          </div>
        </div>
        
        {/* 右侧结果面板 */}
        <div className="lg:col-span-2 space-y-4">
          {/* Progress Panel */}
          <ProgressPanel 
            state={benchmarkState} 
            lang={L} 
            humanScoreCount={humanScores.size}
            onConfirmReview={confirmHumanReview}
          />
          
          {/* 流式日志 */}
          <StreamLog content={streamContent} title={L.streamLog} />
          
          {/* 图表 */}
          {chartData.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="card">
                <h3 className="text-lg font-semibold mb-3">{L.radarChart}</h3>
                <RadarChart data={chartData} />
              </div>
              <div className="card">
                <h3 className="text-lg font-semibold mb-3">{L.barChart}</h3>
                <BarChart data={chartData} />
              </div>
            </div>
          )}
          
          {/* 热力图 */}
          {chartData.length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold mb-3">{L.heatMap}</h3>
              <HeatMap data={chartData} />
            </div>
          )}
          
          {/* 结果表格 */}
          {results.length > 0 && (
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold">{L.results}</h3>
                <div className="flex gap-2 flex-wrap">
                  {/* 阶段3时显示预览按钮 */}
                  {benchmarkState.phase === 'phase3' && (
                    <button 
                      onClick={regenerateCharts}
                      disabled={humanScores.size === 0}
                      className={`px-3 py-1.5 rounded-lg text-sm flex items-center gap-1 transition-colors
                        ${humanScores.size > 0 
                          ? 'bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 text-white'
                          : 'bg-dark-bg border border-dark-border text-dark-muted cursor-not-allowed'
                        }`}
                    >
                      {L.regenerateCharts}{humanScores.size > 0 ? ` (${humanScores.size} ${L.changes})` : ''}
                    </button>
                  )}
                  
                  {/* 阶段4显示已更新标记 */}
                  {benchmarkState.phase === 'phase4' && (
                    <span className="px-3 py-1.5 bg-purple-900/50 text-purple-400 rounded-lg text-sm flex items-center gap-1">
                      {L.correctionsApplied}
                      {` (${humanScores.size})`}
                    </span>
                  )}
                  
                  <button 
                    onClick={exportReport}
                    className="px-3 py-1.5 bg-gradient-to-r from-cyan-600 to-green-600 text-white rounded-lg text-sm hover:from-cyan-500 hover:to-green-500 flex items-center gap-1 font-medium"
                  >
                    {L.exportReport}
                  </button>
                  <button 
                    onClick={exportJson}
                    className="px-3 py-1.5 bg-dark-bg border border-dark-border rounded-lg text-sm hover:border-cyan-500 flex items-center gap-1"
                  >
                    <Download className="w-4 h-4" />
                    {L.exportJson}
                  </button>
                  <button 
                    onClick={exportExcel}
                    className="px-3 py-1.5 bg-dark-bg border border-dark-border rounded-lg text-sm hover:border-cyan-500 flex items-center gap-1"
                  >
                    <Download className="w-4 h-4" />
                    {L.exportExcel}
                  </button>
                </div>
              </div>
              <ResultsTable 
                results={results} 
                evalReasons={evalReasons} 
                humanScores={humanScores}
                onHumanScoreChange={handleHumanScoreChange}
                readonly={false}
              />
            </div>
          )}
        </div>
      </div>
      
      {/* 页脚 */}
      <footer className="text-center text-dark-muted text-sm mt-8 py-4 border-t border-dark-border">
        {L.version}
      </footer>
    </main>
  )
}
