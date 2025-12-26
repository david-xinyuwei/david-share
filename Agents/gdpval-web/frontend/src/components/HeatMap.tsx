'use client'

import { useMemo } from 'react'

interface TaskResult {
  model: string
  sector: string
  overall: number
}

interface HeatMapProps {
  data: TaskResult[]
}

// 颜色插值函数
function getColor(score: number): string {
  // 0-5: 红色到黄色
  // 5-10: 黄色到绿色
  if (score <= 5) {
    const ratio = score / 5
    const r = 239 // #ef4444 红
    const g = Math.round(68 + (234 - 68) * ratio) // 68 -> 234
    const b = Math.round(68 + (179 - 68) * ratio) // 68 -> 179
    return `rgb(${r}, ${g}, ${b})`
  } else {
    const ratio = (score - 5) / 5
    const r = Math.round(234 - (234 - 34) * ratio) // 234 -> 34 (#22c55e 绿)
    const g = Math.round(179 + (197 - 179) * ratio) // 179 -> 197
    const b = Math.round(0 + (94 - 0) * ratio) // 0 -> 94
    return `rgb(${r}, ${g}, ${b})`
  }
}

export function HeatMap({ data }: HeatMapProps) {
  const { models, sectors, matrix, counts } = useMemo(() => {
    const models = [...new Set(data.map(d => d.model))]
    const sectors = [...new Set(data.map(d => d.sector))]
    
    // 计算每个 (model, sector) 组合的平均分和样本数
    const matrix: number[][] = []
    const counts: number[][] = []
    
    models.forEach((model, i) => {
      matrix[i] = []
      counts[i] = []
      sectors.forEach((sector, j) => {
        const items = data.filter(d => d.model === model && d.sector === sector)
        const avg = items.length > 0 
          ? items.reduce((sum, d) => sum + d.overall, 0) / items.length 
          : 0
        matrix[i][j] = avg
        counts[i][j] = items.length
      })
    })
    
    return { models, sectors, matrix, counts }
  }, [data])

  // 计算每个模型的总平均分
  const modelAvgs = useMemo(() => {
    return models.map(model => {
      const items = data.filter(d => d.model === model)
      return items.length > 0 
        ? items.reduce((sum, d) => sum + d.overall, 0) / items.length 
        : 0
    })
  }, [data, models])

  // 计算每个行业的总平均分
  const sectorAvgs = useMemo(() => {
    return sectors.map(sector => {
      const items = data.filter(d => d.sector === sector)
      return items.length > 0 
        ? items.reduce((sum, d) => sum + d.overall, 0) / items.length 
        : 0
    })
  }, [data, sectors])

  // 总样本数
  const totalCount = data.length

  if (models.length === 0 || sectors.length === 0) {
    return <div className="text-dark-muted text-center py-8">No data</div>
  }

  // 简化行业名称
  const shortSector = (s: string) => {
    const map: Record<string, string> = {
      'Professional, Scientific, and Technical Services': 'Prof. Services',
      'Manufacturing': 'Manufacturing',
      'Finance and Insurance': 'Finance',
      'Health Care and Social Assistance': 'Healthcare',
      'Retail Trade': 'Retail',
      'Government': 'Government',
      'Information': 'Information',
      'Real Estate and Rental and Leasing': 'Real Estate',
      'Wholesale Trade': 'Wholesale'
    }
    return map[s] || s.slice(0, 12)
  }

  return (
    <div className="overflow-x-auto">
      <div className="text-sm text-dark-muted mb-2 text-center">
        Total samples: n={totalCount}
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="p-2 text-left text-dark-muted border-b border-dark-border">Model</th>
            {sectors.map((sector, j) => (
              <th 
                key={sector} 
                className="p-2 text-center text-dark-muted border-b border-dark-border text-xs"
                title={sector}
              >
                {shortSector(sector)}
              </th>
            ))}
            <th className="p-2 text-center text-cyan-400 border-b border-dark-border font-bold">Avg</th>
          </tr>
        </thead>
        <tbody>
          {models.map((model, i) => (
            <tr key={model}>
              <td className="p-2 text-dark-text border-b border-dark-border whitespace-nowrap">
                {model}
              </td>
              {sectors.map((sector, j) => {
                const score = matrix[i][j]
                const count = counts[i][j]
                return (
                  <td 
                    key={sector}
                    className="p-2 text-center border-b border-dark-border"
                    style={{ backgroundColor: count > 0 ? getColor(score) : '#1f2937' }}
                    title={`${model} × ${sector}: ${score.toFixed(1)} (n=${count})`}
                  >
                    {count > 0 ? (
                      <span className="text-white font-medium text-xs drop-shadow-md">
                        {score.toFixed(1)}
                      </span>
                    ) : (
                      <span className="text-gray-500">-</span>
                    )}
                  </td>
                )
              })}
              <td 
                className="p-2 text-center border-b border-dark-border font-bold"
                style={{ backgroundColor: getColor(modelAvgs[i]) }}
              >
                <span className="text-white drop-shadow-md">{modelAvgs[i].toFixed(1)}</span>
              </td>
            </tr>
          ))}
          {/* 行业平均行 */}
          <tr className="bg-dark-card">
            <td className="p-2 text-cyan-400 font-bold">Avg</td>
            {sectorAvgs.map((avg, j) => (
              <td 
                key={j}
                className="p-2 text-center font-bold"
                style={{ backgroundColor: getColor(avg) }}
              >
                <span className="text-white drop-shadow-md">{avg.toFixed(1)}</span>
              </td>
            ))}
            <td className="p-2 text-center font-bold text-cyan-400">
              {(data.reduce((sum, d) => sum + d.overall, 0) / data.length).toFixed(1)}
            </td>
          </tr>
        </tbody>
      </table>
      
      {/* 图例 */}
      <div className="flex items-center justify-center gap-4 mt-4 text-xs text-dark-muted">
        <span>Score:</span>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: getColor(0) }}></div>
          <span>0</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: getColor(5) }}></div>
          <span>5</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: getColor(10) }}></div>
          <span>10</span>
        </div>
      </div>
    </div>
  )
}
