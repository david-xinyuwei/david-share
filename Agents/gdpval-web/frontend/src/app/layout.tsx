import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: '🎯 GDPVAL Grok Benchmark Tool',
  description: 'AI Model Evaluation on Real-World Economically Valuable Tasks',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh" className="dark">
      <body className="min-h-screen bg-dark-bg text-dark-text antialiased">
        {children}
      </body>
    </html>
  )
}
