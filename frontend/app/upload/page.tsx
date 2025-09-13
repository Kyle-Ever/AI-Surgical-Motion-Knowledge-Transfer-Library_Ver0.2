'use client'

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import { Upload, X, FileVideo, ChevronRight, Loader2 } from 'lucide-react'
import { formatFileSize } from '@/lib/utils'
import { useUploadVideo, useStartAnalysis } from '@/hooks/useApi'

export default function UploadPage() {
  const router = useRouter()
  const { uploadVideo, progress: uploadProgress } = useUploadVideo()
  const { startAnalysis } = useStartAnalysis()

  const [file, setFile] = useState<File | null>(null)
  const [formData, setFormData] = useState({ surgeryName: '', surgeryDate: '', surgeonName: '', memo: '' })
  const [videoType, setVideoType] = useState<'internal' | 'external' | null>(null)
  const [step, setStep] = useState<'upload' | 'type' | 'annotation'>('upload')
  const [isUploading, setIsUploading] = useState(false)

  const onDrop = useCallback((acceptedFiles: File[]) => { if (acceptedFiles.length > 0) setFile(acceptedFiles[0]) }, [])
  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept: { 'video/mp4': ['.mp4'] }, maxSize: 2*1024*1024*1024, multiple: false })

  const handleRemoveFile = () => { setFile(null); setStep('upload') }
  const handleNext = () => {
    if (step === 'upload' && file) setStep('type')
    else if (step === 'type' && videoType) { if (videoType === 'internal') setStep('annotation'); else void handleStartAnalysis() }
  }
  const handleStartAnalysis = async () => {
    if (!file || !videoType) return
    try {
      setIsUploading(true)
      const uploadResponse = await uploadVideo(file, { video_type: videoType, surgery_name: formData.surgeryName, surgery_date: formData.surgeryDate, surgeon_name: formData.surgeonName, memo: formData.memo })
      const videoId = uploadResponse.video_id
      const analysisResponse = await startAnalysis(videoId)
      router.push(`/analysis/${analysisResponse.id}`)
    } catch (e: any) { console.error(e); alert(e?.message || 'エラーが発生しました') } finally { setIsUploading(false) }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">動画アップロード</h1>
        <div className="flex items-center mt-4 space-x-2">
          <div className={`flex items-center ${step==='upload'?'text-blue-600':'text-gray-400'}`}><span className="mr-2">1. アップロード</span></div>
          <ChevronRight className="w-4 h-4 text-gray-400" />
          <div className={`flex items-center ${step==='type'?'text-blue-600':'text-gray-400'}`}><span className="mr-2">2. 映像タイプ</span></div>
          {videoType==='internal' && (<><ChevronRight className="w-4 h-4 text-gray-400" /><div className={`flex items-center ${step==='annotation'?'text-blue-600':'text-gray-400'}`}><span className="mr-2">3. アノテーション</span></div></>)}
        </div>
      </div>
      {step==='upload' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            {!file ? (
              <div {...getRootProps()} className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${isDragActive?'border-blue-500 bg-blue-50':'border-gray-300 hover:border-blue-400'}`}>
                <input {...getInputProps()} />
                <Upload className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                <p className="text-gray-600 mb-2">動画ファイルをドラッグ＆ドロップ</p>
                <p className="text-sm text-gray-500">または</p>
                <button className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">ファイルを選択</button>
                <p className="text-xs text-gray-500 mt-4">対応形式: MP4（最大2GB）</p>
              </div>
            ) : (
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <FileVideo className="w-8 h-8 text-blue-600" />
                  <div>
                    <p className="font-medium text-gray-900">{file.name}</p>
                    <p className="text-sm text-gray-500">{formatFileSize(file.size)}</p>
                  </div>
                </div>
                <button onClick={handleRemoveFile} className="p-1 hover:bg-gray-200 rounded" aria-label="ファイルを削除"><X className="w-5 h-5 text-gray-600" /></button>
              </div>
            )}
          </div>
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">任意情報</h2>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="block text-sm font-medium text-gray-700 mb-1">手術名</label><input type="text" value={formData.surgeryName} onChange={(e)=>setFormData({ ...formData, surgeryName:e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="例: 腹腔鏡手術" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">手術日</label><input type="date" value={formData.surgeryDate} onChange={(e)=>setFormData({ ...formData, surgeryDate:e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">執刀医</label><input type="text" value={formData.surgeonName} onChange={(e)=>setFormData({ ...formData, surgeonName:e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="例: 山田医師" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">メモ</label><input type="text" value={formData.memo} onChange={(e)=>setFormData({ ...formData, memo:e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" /></div>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <button disabled={!file} onClick={handleNext} className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50">次へ</button>
            {isUploading && (<div className="flex items-center text-sm text-gray-500"><Loader2 className="w-4 h-4 mr-2 animate-spin" /> アップロード中... {uploadProgress}%</div>)}
          </div>
        </div>
      )}
      {step==='type' && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">映像タイプを選択</h2>
          <div className="flex space-x-4">
            <button onClick={()=>setVideoType('external')} className={`px-4 py-2 rounded-md border ${videoType==='external'?'bg-blue-600 text-white':'bg-white'}`}>外部（手元カメラ）</button>
            <button onClick={()=>setVideoType('internal')} className={`px-4 py-2 rounded-md border ${videoType==='internal'?'bg-blue-600 text-white':'bg-white'}`}>内視鏡（術野カメラ）</button>
          </div>
          <div className="flex items-center justify-between">
            <button onClick={()=>setStep('upload')} className="px-4 py-2 border rounded-md">戻る</button>
            <button onClick={handleNext} disabled={!videoType} className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50">次へ</button>
          </div>
        </div>
      )}
      {step==='annotation' && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">アノテーション</h2>
          <p className="text-gray-600">簡易アノテーションは後続で対応予定です。まずは解析を開始してください。</p>
          <div className="flex items-center justify-end"><button onClick={handleStartAnalysis} className="px-4 py-2 bg-blue-600 text-white rounded-md">解析を開始</button></div>
        </div>
      )}
    </div>
  )
}
