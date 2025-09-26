'use client'

import { useState, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import { Upload, X, FileVideo, ChevronRight, Loader2, Camera, List } from 'lucide-react'
import { formatFileSize } from '@/lib/utils'
import { useUploadVideo, useStartAnalysis } from '@/hooks/useApi'
import dynamic from 'next/dynamic'

// Dynamically import InstrumentSelector to avoid SSR issues
const InstrumentSelector = dynamic(() => import('@/components/InstrumentSelector'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-96">
      <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
    </div>
  )
})

export default function UploadPage() {
  const router = useRouter()
  const { uploadVideo, progress: uploadProgress } = useUploadVideo()
  const { startAnalysis } = useStartAnalysis()

  // デバッグ用
  useEffect(() => {
    console.log('UploadPage mounted')
    console.log('open function available:', typeof open)
    return () => {
      console.log('UploadPage unmounted')
    }
  }, [])

  const [file, setFile] = useState<File | null>(null)
  const [formData, setFormData] = useState({
    surgeryName: '',
    surgeryDate: '',
    surgeonName: '',
    memo: ''
  })
  const [videoType, setVideoType] = useState<'internal' | 'external' | null>(null)
  const [step, setStep] = useState<'upload' | 'type' | 'instruments' | 'annotation'>('upload')
  const [isUploading, setIsUploading] = useState(false)
  const [selectedInstruments, setSelectedInstruments] = useState<string[]>([])
  const [uploadedVideoId, setUploadedVideoId] = useState<string | null>(null)
  const [instrumentSelectionMode, setInstrumentSelectionMode] = useState<'checkbox' | 'sam'>('checkbox')
  const [samSelectedInstruments, setSamSelectedInstruments] = useState<any[]>([])

  // Available surgical instruments
  const availableInstruments = [
    { id: 'forceps', name: 'Forceps', description: '鉗子' },
    { id: 'scissors', name: 'Scissors', description: 'はさみ' },
    { id: 'needle_holder', name: 'Needle Holder', description: '持針器' },
    { id: 'scalpel', name: 'Scalpel', description: 'メス' },
    { id: 'retractor', name: 'Retractor', description: 'リトラクター' },
    { id: 'suction', name: 'Suction', description: '吸引器' },
    { id: 'cautery', name: 'Cautery', description: '電気メス' },
    { id: 'clamp', name: 'Clamp', description: 'クランプ' },
  ]

  const onDrop = useCallback((acceptedFiles: File[]) => {
    console.log('onDrop called:', acceptedFiles)
    if (acceptedFiles.length > 0) {
      console.log('File accepted:', acceptedFiles[0].name)
      setFile(acceptedFiles[0])
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: { 'video/mp4': ['.mp4'] },
    maxSize: 2 * 1024 * 1024 * 1024,
    multiple: false,
    noClick: true, // Disable click on dropzone area to prevent conflicts with button
    onDropRejected: (fileRejections) => {
      console.error('Files rejected:', fileRejections)
      fileRejections.forEach((file) => {
        console.error('Rejection reasons:', file.errors)
      })
    },
    onError: (err) => {
      console.error('Dropzone error:', err)
    }
  })

  const handleRemoveFile = () => {
    setFile(null)
    setStep('upload')
  }

  const toggleInstrument = (instrumentId: string) => {
    setSelectedInstruments(prev =>
      prev.includes(instrumentId)
        ? prev.filter(id => id !== instrumentId)
        : [...prev, instrumentId]
    )
  }

  const handleNext = () => {
    if (step === 'upload' && file) {
      setStep('type')
    } else if (step === 'type' && videoType) {
      // For internal videos or external with instruments, show instrument selection
      if (videoType === 'internal' || videoType === 'external_with_instruments') {
        setStep('instruments')
      } else {
        // For external without instruments, skip to annotation
        setStep('annotation')
      }
    } else if (step === 'instruments') {
      setStep('annotation')
    }
  }

  const handleVideoUpload = async () => {
    if (!file || !videoType) return null

    try {
      // Upload video
      const uploadResponse = await uploadVideo(file, {
        video_type: videoType,
        surgery_name: formData.surgeryName,
        surgery_date: formData.surgeryDate,
        surgeon_name: formData.surgeonName,
        memo: formData.memo
      })

      return uploadResponse.video_id
    } catch (e: any) {
      console.error(e)
      alert(e?.message || 'Upload failed')
      return null
    }
  }

  const handleStartAnalysis = async () => {
    if (!file || !videoType) return

    try {
      setIsUploading(true)

      // Get or upload video
      let videoId = uploadedVideoId
      if (!videoId) {
        videoId = await handleVideoUpload()
        if (!videoId) {
          throw new Error('Failed to upload video')
        }
        setUploadedVideoId(videoId)
      }

      // Prepare instruments data for analysis
      let instruments: any[] = []
      if (videoType === 'internal' || videoType === 'external_with_instruments') {
        if (instrumentSelectionMode === 'sam' && samSelectedInstruments.length > 0) {
          // Use SAM-selected instruments
          instruments = samSelectedInstruments.map(inst => ({
            name: inst.name,
            mask: inst.mask,
            bbox: inst.bbox
          }))
        } else if (selectedInstruments.length > 0) {
          // Use checkbox-selected instruments
          instruments = selectedInstruments.map(id => {
            const instrument = availableInstruments.find(i => i.id === id)
            return { name: instrument?.name || id }
          })
        }
      }

      // Start analysis with instruments
      const analysisResponse = await startAnalysis(videoId, instruments)
      router.push(`/analysis/${analysisResponse.id}`)
    } catch (e: any) {
      console.error(e)
      alert(e?.message || 'エラーが発生しました')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900" data-testid="upload-title">
          動画アップロード
        </h1>
        <div className="flex items-center mt-4 space-x-2">
          <div className={`flex items-center ${step === 'upload' ? 'text-blue-600' : 'text-gray-400'}`}>
            <span className="mr-2">1. アップロード</span>
          </div>
          <ChevronRight className="w-4 h-4 text-gray-400" />
          <div className={`flex items-center ${step === 'type' ? 'text-blue-600' : 'text-gray-400'}`}>
            <span className="mr-2">2. 映像タイプ</span>
          </div>
          {(videoType === 'internal' || videoType === 'external_with_instruments') && (
            <>
              <ChevronRight className="w-4 h-4 text-gray-400" />
              <div className={`flex items-center ${step === 'instruments' ? 'text-blue-600' : 'text-gray-400'}`}>
                <span className="mr-2">3. 器具選択</span>
              </div>
            </>
          )}
          <ChevronRight className="w-4 h-4 text-gray-400" />
          <div className={`flex items-center ${step === 'annotation' ? 'text-blue-600' : 'text-gray-400'}`}>
            <span className="mr-2">{(videoType === 'internal' || videoType === 'external_with_instruments') ? '4' : '3'}. 解析設定</span>
          </div>
        </div>
      </div>

      {step === 'upload' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            {!file ? (
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
                  isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
                }`}
              >
                <input {...getInputProps()} data-testid="file-input" />
                <Upload className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                <p className="text-gray-600 mb-2">動画ファイルをドラッグ＆ドロップ</p>
                <p className="text-sm text-gray-500">または</p>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    console.log('Button clicked, calling open()', open)
                    if (open) {
                      open()
                    } else {
                      console.error('open function not available')
                    }
                  }}
                  className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                  data-testid="file-select-button"
                >
                  ファイルを選択
                </button>
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
                <button
                  onClick={handleRemoveFile}
                  className="p-1 hover:bg-gray-200 rounded"
                  aria-label="ファイルを削除"
                >
                  <X className="w-5 h-5 text-gray-600" />
                </button>
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">任意情報</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">手術名</label>
                <input
                  type="text"
                  value={formData.surgeryName}
                  onChange={(e) => setFormData({ ...formData, surgeryName: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="例: 腹腔鏡手術"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">手術日</label>
                <input
                  type="date"
                  value={formData.surgeryDate}
                  onChange={(e) => setFormData({ ...formData, surgeryDate: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">執刀医</label>
                <input
                  type="text"
                  value={formData.surgeonName}
                  onChange={(e) => setFormData({ ...formData, surgeonName: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="例: 山田医師"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">メモ</label>
                <input
                  type="text"
                  value={formData.memo}
                  onChange={(e) => setFormData({ ...formData, memo: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <button
              disabled={!file}
              onClick={handleNext}
              className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50"
              data-testid="next-button"
            >
              次へ
            </button>
            {isUploading && (
              <div className="flex items-center text-sm text-gray-500">
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                アップロード中... {uploadProgress}%
              </div>
            )}
          </div>
        </div>
      )}

      {step === 'type' && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">映像タイプを選択</h2>
          <div className="grid grid-cols-3 gap-4">
            <button
              onClick={() => setVideoType('external_no_instruments')}
              className={`p-6 rounded-lg border-2 transition-all ${
                videoType === 'external_no_instruments'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="text-left">
                <h3 className="font-semibold mb-2">外部カメラ<br/>（器具なし）</h3>
                <p className="text-sm text-gray-600">
                  手術者の手の動きを外部から撮影
                </p>
                <p className="text-xs text-gray-500 mt-2">
                  検出対象: 手の骨格のみ
                </p>
              </div>
            </button>
            <button
              onClick={() => setVideoType('external_with_instruments')}
              className={`p-6 rounded-lg border-2 transition-all ${
                videoType === 'external_with_instruments'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="text-left">
                <h3 className="font-semibold mb-2">外部カメラ<br/>（器具あり）</h3>
                <p className="text-sm text-gray-600">
                  器具を使用した手術の外部撮影
                </p>
                <p className="text-xs text-gray-500 mt-2">
                  検出対象: 手の骨格 + 器具
                </p>
              </div>
            </button>
            <button
              onClick={() => setVideoType('internal')}
              className={`p-6 rounded-lg border-2 transition-all ${
                videoType === 'internal'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="text-left">
                <h3 className="font-semibold mb-2">内視鏡<br/>（術野カメラ）</h3>
                <p className="text-sm text-gray-600">
                  内視鏡による術野の映像
                </p>
                <p className="text-xs text-gray-500 mt-2">
                  検出対象: 手の骨格 + 器具
                </p>
              </div>
            </button>
          </div>
          <div className="flex items-center justify-between">
            <button onClick={() => setStep('upload')} className="px-4 py-2 border rounded-md">
              戻る
            </button>
            <button
              onClick={handleNext}
              disabled={!videoType}
              className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50"
            >
              次へ
            </button>
          </div>
        </div>
      )}

      {step === 'instruments' && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold mb-2">使用器具の選択</h2>
            <p className="text-sm text-gray-600 mb-4">
              内視鏡映像で使用している手術器具を選択してください。
            </p>

            {/* Selection mode toggle */}
            <div className="flex items-center space-x-4 mb-6">
              <button
                onClick={() => setInstrumentSelectionMode('checkbox')}
                className={`flex items-center px-4 py-2 rounded-md ${
                  instrumentSelectionMode === 'checkbox'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <List className="w-4 h-4 mr-2" />
                リストから選択
              </button>
              <button
                onClick={async () => {
                  // Upload video first if not already uploaded
                  if (!uploadedVideoId) {
                    const videoId = await handleVideoUpload()
                    if (videoId) {
                      setUploadedVideoId(videoId)
                      setInstrumentSelectionMode('sam')
                    } else {
                      alert('動画のアップロードが必要です')
                    }
                  } else {
                    setInstrumentSelectionMode('sam')
                  }
                }}
                className={`flex items-center px-4 py-2 rounded-md ${
                  instrumentSelectionMode === 'sam'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <Camera className="w-4 h-4 mr-2" />
                映像から直接選択 (SAM)
              </button>
            </div>
          </div>

          {instrumentSelectionMode === 'checkbox' ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                {availableInstruments.map(instrument => (
                  <label
                    key={instrument.id}
                    className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedInstruments.includes(instrument.id)}
                      onChange={() => toggleInstrument(instrument.id)}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                    <div className="flex-1">
                      <div className="font-medium">{instrument.name}</div>
                      <div className="text-sm text-gray-500">{instrument.description}</div>
                    </div>
                  </label>
                ))}
              </div>

              {selectedInstruments.length === 0 && (
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="text-sm text-yellow-800">
                    ⚠️ 器具を選択しない場合、器具検出は行われません。
                    手の骨格のみが検出されます。
                  </p>
                </div>
              )}
            </>
          ) : (
            <InstrumentSelector
              videoId={uploadedVideoId!}
              onInstrumentsSelected={(instruments) => {
                setSamSelectedInstruments(instruments)
                setStep('annotation')
              }}
              onBack={() => setInstrumentSelectionMode('checkbox')}
            />
          )}

          {instrumentSelectionMode === 'checkbox' && (
            <div className="flex items-center justify-between">
              <button onClick={() => setStep('type')} className="px-4 py-2 border rounded-md">
                戻る
              </button>
              <button onClick={handleNext} className="px-4 py-2 bg-blue-600 text-white rounded-md">
                次へ
              </button>
            </div>
          )}
        </div>
      )}

      {step === 'annotation' && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">解析設定の確認</h2>

          <div className="space-y-3 bg-gray-50 p-4 rounded-lg">
            <div className="flex justify-between">
              <span className="text-gray-600">映像タイプ:</span>
              <span className="font-medium">
                {videoType === 'external_no_instruments' ? '外部カメラ（器具なし）' :
                 videoType === 'external_with_instruments' ? '外部カメラ（器具あり）' :
                 videoType === 'external' ? '外部（手元カメラ）' : '内視鏡（術野カメラ）'}
              </span>
            </div>

            {(videoType === 'internal' || videoType === 'external_with_instruments') && (
              <div className="flex justify-between">
                <span className="text-gray-600">選択した器具:</span>
                <span className="font-medium">
                  {instrumentSelectionMode === 'sam' && samSelectedInstruments.length > 0
                    ? samSelectedInstruments.map(inst => inst.name).join(', ')
                    : selectedInstruments.length > 0
                    ? selectedInstruments
                        .map(id => availableInstruments.find(i => i.id === id)?.name)
                        .join(', ')
                    : 'なし（器具検出を行いません）'}
                </span>
              </div>
            )}

            <div className="flex justify-between">
              <span className="text-gray-600">検出対象:</span>
              <span className="font-medium">
                {videoType === 'external'
                  ? '手の骨格（21ポイント）'
                  : (instrumentSelectionMode === 'sam' && samSelectedInstruments.length > 0) || selectedInstruments.length > 0
                  ? '手の骨格 + 選択した器具'
                  : '手の骨格のみ'}
              </span>
            </div>
          </div>

          <p className="text-sm text-gray-600">
            詳細なアノテーション機能は今後のアップデートで追加予定です。
          </p>

          <div className="flex items-center justify-between">
            <button
              onClick={() => setStep((videoType === 'internal' || videoType === 'external_with_instruments') ? 'instruments' : 'type')}
              className="px-4 py-2 border rounded-md"
            >
              戻る
            </button>
            <button
              onClick={handleStartAnalysis}
              className="px-4 py-2 bg-blue-600 text-white rounded-md"
              disabled={isUploading}
            >
              {isUploading ? (
                <span className="flex items-center">
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  処理中...
                </span>
              ) : (
                '解析を開始'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}