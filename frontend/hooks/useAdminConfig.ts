"use client"

import { useState, useEffect, useCallback } from "react"
import { api, endpoints } from "@/lib/api"

export interface MetricsConfig {
  weights: {
    a1: number; a2: number; a3: number
    b1: number; b2: number; b3: number
    group_a: number; group_b: number
  }
  thresholds: {
    idle_velocity_threshold: number
    idle_velocity_threshold_pixel: number
    micro_pause_max_sec: number
    check_pause_max_sec: number
    movement_velocity_threshold: number
    movement_velocity_threshold_pixel: number
    smoothing_window: number
    hysteresis_ratio: number
    adaptive_threshold: boolean
    idle_percentile: number
    movement_percentile: number
  }
  scoring: {
    a1_max_path_pixel: number
    a1_max_path_normalized: number
    a2_sparc_min: number
    a2_sparc_max: number
    a3_both_hands_min_ratio: number
    a3_correlation_weight: number
    a3_balance_weight: number
    b1_max_idle_ratio: number
    b2_max_movements_per_minute: number
    b3_max_area_pixel: number
    b3_max_area_normalized: number
  }
  sparc: {
    freq_cutoff_hz: number
    amplitude_threshold: number
  }
}

export function useAdminConfig() {
  const [config, setConfig] = useState<MetricsConfig | null>(null)
  const [defaults, setDefaults] = useState<MetricsConfig | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const fetchConfig = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [configRes, defaultsRes] = await Promise.all([
        api.get(endpoints.admin.getMetricsConfig),
        api.get(endpoints.admin.getMetricsDefaults),
      ])
      setConfig(configRes.data)
      setDefaults(defaultsRes.data)
    } catch (e: any) {
      setError(e.message || "設定の取得に失敗しました")
    } finally {
      setIsLoading(false)
    }
  }, [])

  const saveConfig = useCallback(async (updated: MetricsConfig) => {
    setIsSaving(true)
    setError(null)
    setSaveSuccess(false)
    try {
      const res = await api.put(endpoints.admin.updateMetricsConfig, updated)
      setConfig(res.data)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (e: any) {
      const detail = e.response?.data?.detail || e.message || "保存に失敗しました"
      setError(detail)
      throw e
    } finally {
      setIsSaving(false)
    }
  }, [])

  const resetConfig = useCallback(async () => {
    setIsSaving(true)
    setError(null)
    try {
      const res = await api.post(endpoints.admin.resetMetricsConfig)
      setConfig(res.data)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (e: any) {
      setError(e.message || "リセットに失敗しました")
    } finally {
      setIsSaving(false)
    }
  }, [])

  useEffect(() => {
    fetchConfig()
  }, [fetchConfig])

  return { config, defaults, isLoading, isSaving, error, saveSuccess, saveConfig, resetConfig, fetchConfig }
}
