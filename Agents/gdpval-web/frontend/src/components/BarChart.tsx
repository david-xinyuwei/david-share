'use client'

import {
  BarChart as RechartsBar,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList
} from 'recharts'

interface TaskResult {
  model: string
  overall: number
}

interface BarChartProps {
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

export function BarChart({ data }: BarChartProps) {
  // 按模型聚合，计算平均分
  const models = [...new Set(data.map(d => d.model))]
  
  const chartData = models.map((model, idx) => {
    const modelData = data.filter(d => d.model === model)
    const avg = modelData.reduce((sum, d) => sum + d.overall, 0) / modelData.length
    return {
      model: model.replace('grok-', ''),
      fullModel: model,
      score: Number(avg.toFixed(2)),
      count: modelData.length,
      color: COLORS[idx % COLORS.length]
    }
  }).sort((a, b) => b.score - a.score)
  
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <RechartsBar data={chartData} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            type="number" 
            domain={[0, 10]} 
            tick={{ fill: '#9ca3af', fontSize: 12 }}
          />
          <YAxis 
            type="category" 
            dataKey="model" 
            tick={{ fill: '#9ca3af', fontSize: 11 }}
            width={100}
          />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: '#1a1f2e', 
              border: '1px solid #374151',
              borderRadius: '8px'
            }}
            formatter={(value: number, name: string, props: any) => [
              `${value}/10 (n=${props.payload.count})`,
              '综合得分'
            ]}
          />
          <Bar 
            dataKey="score" 
            radius={[0, 4, 4, 0]}
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
            <LabelList 
              dataKey="score" 
              position="right" 
              fill="#e2e8f0"
              fontSize={12}
              formatter={(v: number) => v.toFixed(1)}
            />
          </Bar>
        </RechartsBar>
      </ResponsiveContainer>
    </div>
  )
}
