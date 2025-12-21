'use client'

import {
  Radar,
  RadarChart as RechartsRadar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip
} from 'recharts'

interface TaskResult {
  model: string
  completeness: number
  accuracy: number
  professionalism: number
  clarity: number
  actionability: number
}

interface RadarChartProps {
  data: TaskResult[]
}

const COLORS = [
  '#06b6d4', // cyan
  '#a855f7', // purple
  '#f97316', // orange
  '#22c55e', // green
  '#ef4444', // red
  '#3b82f6', // blue
]

const DIMENSIONS = [
  { key: 'completeness', label: 'Complete' },
  { key: 'accuracy', label: 'Accurate' },
  { key: 'professionalism', label: 'Professional' },
  { key: 'clarity', label: 'Clarity' },
  { key: 'actionability', label: 'Actionable' },
]

export function RadarChart({ data }: RadarChartProps) {
  // 按模型聚合数据
  const models = [...new Set(data.map(d => d.model))]
  
  const chartData = DIMENSIONS.map(dim => {
    const point: any = { dimension: dim.label }
    models.forEach(model => {
      const modelData = data.filter(d => d.model === model)
      const avg = modelData.reduce((sum, d) => sum + (d[dim.key as keyof TaskResult] as number || 0), 0) / modelData.length
      point[model] = Number(avg.toFixed(2))
    })
    return point
  })
  
  // 计算样本数
  const sampleCounts = models.map(model => {
    const count = data.filter(d => d.model === model).length
    return `${model} (n=${count})`
  })
  
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <RechartsRadar data={chartData}>
          <PolarGrid stroke="#374151" />
          <PolarAngleAxis 
            dataKey="dimension" 
            tick={{ fill: '#9ca3af', fontSize: 12 }}
          />
          <PolarRadiusAxis 
            angle={90} 
            domain={[0, 10]} 
            tick={{ fill: '#9ca3af', fontSize: 10 }}
          />
          {models.map((model, idx) => (
            <Radar
              key={model}
              name={`${model} (n=${data.filter(d => d.model === model).length})`}
              dataKey={model}
              stroke={COLORS[idx % COLORS.length]}
              fill={COLORS[idx % COLORS.length]}
              fillOpacity={0.2}
              strokeWidth={2}
            />
          ))}
          <Legend 
            wrapperStyle={{ fontSize: '12px' }}
          />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: '#1a1f2e', 
              border: '1px solid #374151',
              borderRadius: '8px'
            }}
          />
        </RechartsRadar>
      </ResponsiveContainer>
    </div>
  )
}
