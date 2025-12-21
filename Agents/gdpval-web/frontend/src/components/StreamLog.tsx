'use client'

import { useRef, useEffect } from 'react'

interface StreamLogProps {
  content: string
  title: string
}

export function StreamLog({ content, title }: StreamLogProps) {
  const logRef = useRef<HTMLDivElement>(null)
  
  // 自动滚动到底部
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [content])
  
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
        📜 {title}
      </h3>
      <div 
        ref={logRef}
        className="stream-log h-80 overflow-auto"
      >
        <pre className="text-green-400 whitespace-pre-wrap">
          {content || 'Waiting for benchmark...'}
        </pre>
      </div>
    </div>
  )
}
