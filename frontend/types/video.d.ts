/**
 * requestVideoFrameCallback API の型定義
 *
 * Chrome 83+, Edge 83+, Safari 15.4+ で対応
 * Firefox は未対応（2025年1月時点）
 *
 * 参考: https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback
 */

/**
 * ビデオフレームのメタデータ
 */
interface VideoFrameMetadata {
  /**
   * フレームが提示された時刻（DOMHighResTimeStamp）
   */
  presentationTime: DOMHighResTimeStamp

  /**
   * フレームが画面に表示されると予想される時刻
   */
  expectedDisplayTime: DOMHighResTimeStamp

  /**
   * フレームの幅（ピクセル）
   */
  width: number

  /**
   * フレームの高さ（ピクセル）
   */
  height: number

  /**
   * ビデオの現在のメディア時刻（秒）
   * video.currentTime と同等だが、より正確
   */
  mediaTime: number

  /**
   * これまでに提示されたフレームの総数
   */
  presentedFrames: number

  /**
   * フレーム処理にかかった時間（オプション）
   */
  processingDuration?: number
}

/**
 * ビデオフレームコールバック関数の型
 */
type VideoFrameRequestCallback = (
  now: DOMHighResTimeStamp,
  metadata: VideoFrameMetadata
) => void

/**
 * HTMLVideoElement の拡張（RVFC対応）
 */
interface HTMLVideoElement {
  /**
   * ビデオフレームごとにコールバックを実行
   *
   * @param callback 実行するコールバック関数
   * @returns コールバックのハンドルID（キャンセル用）
   */
  requestVideoFrameCallback?: (
    callback: VideoFrameRequestCallback
  ) => number

  /**
   * requestVideoFrameCallback で登録したコールバックをキャンセル
   *
   * @param handle requestVideoFrameCallback が返したハンドルID
   */
  cancelVideoFrameCallback?: (handle: number) => void
}
