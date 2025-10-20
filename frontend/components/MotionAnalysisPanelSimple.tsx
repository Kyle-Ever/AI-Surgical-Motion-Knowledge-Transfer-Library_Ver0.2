'use client'

import { useState, useEffect } from 'react'

export default function MotionAnalysisPanelSimple() {
  const [value, setValue] = useState(50)

  useEffect(() => {
    console.log('[MotionAnalysisPanelSimple] Component mounted, value:', value)
    const interval = setInterval(() => {
      setValue(prev => {
        const newValue = 50 + Math.sin(Date.now() / 1000) * 30
        console.log('[MotionAnalysisPanelSimple] Updating value:', newValue)
        return newValue
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [])

  console.log('[MotionAnalysisPanelSimple] Rendering with value:', value)

  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-lg font-semibold mb-4">手技の動き分析（テスト）</h2>

      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span>速度</span>
            <span className="font-medium">{value.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${value}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
