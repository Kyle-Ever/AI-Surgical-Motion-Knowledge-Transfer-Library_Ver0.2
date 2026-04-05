"""
Result formatting functions extracted from AnalysisServiceV2.

Pure functions for transforming detection results into frontend-compatible formats.
Uses ExtractionResult for accurate frame index and timestamp mapping.
"""
import json
import logging
from collections import defaultdict
from typing import Dict, List, Any, Optional

import numpy as np

from .data_converter import extract_mask_contour
from .frame_extraction_service import ExtractionResult

logger = logging.getLogger(__name__)


def format_skeleton_data(
    raw_results: List[Dict],
    extraction_result: Optional[ExtractionResult],
    video_info: Dict[str, Any] = None,
) -> List[Dict]:
    """
    骨格検出結果をフォーマット（フロントエンド互換形式）

    extraction_resultのframe_indicesとtimestampsを使用して正確なマッピング

    Args:
        raw_results: 骨格検出の生結果リスト
        extraction_result: フレーム抽出結果（frame_indices, timestamps）
        video_info: 動画情報（fpsなど）。extraction_resultがない場合のフォールバック用。

    Returns:
        フロントエンド互換のフォーマット済み骨格データリスト
    """
    if video_info is None:
        video_info = {}

    # extraction_resultがない場合のフォールバック
    if not extraction_result:
        logger.error("[ANALYSIS] extraction_result not available, using fallback")
        fps = video_info.get('fps', 30)
        from app.core.config import settings
        target_fps = getattr(settings, 'FRAME_EXTRACTION_FPS', 15)
        frame_skip = max(1, int(fps / target_fps))

        frames_dict = defaultdict(list)
        for result in raw_results:
            if not isinstance(result, dict):
                continue
            if result.get('detected'):
                if 'frame_index' not in result:
                    raise ValueError(f"Missing frame_index in skeleton result")
                frame_idx = result['frame_index']
                actual_frame_number = frame_idx * frame_skip
                timestamp = actual_frame_number / fps if fps > 0 else frame_idx / 30.0

                for hand in result.get('hands', []):
                    hand_data = {
                        'hand_type': hand.get('hand_type', hand.get('label', 'Unknown')),
                        'landmarks': hand.get('landmarks', {}),
                        'palm_center': hand.get('palm_center', {}),
                        'finger_angles': hand.get('finger_angles', {}),
                        'hand_openness': hand.get('hand_openness', 0.0)
                    }
                    frames_dict[actual_frame_number].append(hand_data)

        formatted = []
        for frame_number in sorted(frames_dict.keys()):
            timestamp = frame_number / fps if fps > 0 else frame_number / 30.0
            formatted.append({
                'frame': frame_number,
                'frame_number': frame_number,
                'timestamp': timestamp,
                'hands': frames_dict[frame_number]
            })
        return formatted

    # 新しいロジック: extraction_resultを使用
    logger.info(f"[ANALYSIS] _format_skeleton_data using extraction_result: "
               f"{len(extraction_result.frame_indices)} frame_indices, "
               f"{len(extraction_result.timestamps)} timestamps")

    frames_dict = defaultdict(list)
    for result in raw_results:
        if not isinstance(result, dict):
            logger.warning(f"Skipping non-dict result: type={type(result)}")
            continue
        if result.get('detected'):
            # Fail Fast: frame_indexが存在しない場合はエラー
            if 'frame_index' not in result:
                error_msg = f"Missing frame_index in skeleton detection result. Result keys: {list(result.keys())}"
                logger.error(error_msg)
                raise ValueError(f"skeleton_detector.detect_batch() must include frame_index in results. {error_msg}")

            frame_idx = result['frame_index']

            # extraction_resultから正確な値を取得
            if frame_idx >= len(extraction_result.frame_indices):
                logger.warning(f"[ANALYSIS] Frame {frame_idx} exceeds extraction_result length")
                continue

            actual_frame_number = extraction_result.frame_indices[frame_idx]
            timestamp = extraction_result.timestamps[frame_idx]

            for hand in result.get('hands', []):
                hand_data = {
                    'hand_type': hand.get('hand_type', hand.get('label', 'Unknown')),
                    'landmarks': hand.get('landmarks', {}),
                    'palm_center': hand.get('palm_center', {}),
                    'finger_angles': hand.get('finger_angles', {}),
                    'hand_openness': hand.get('hand_openness', 0.0)
                }
                frames_dict[actual_frame_number].append(hand_data)

    # フロントエンド形式に変換: 1フレーム = 1レコード（複数の手を含む）
    formatted = []
    for frame_number in sorted(frames_dict.keys()):
        # extraction_resultから対応するタイムスタンプを取得
        frame_idx = extraction_result.frame_indices.index(frame_number) if frame_number in extraction_result.frame_indices else None
        if frame_idx is not None:
            timestamp = extraction_result.timestamps[frame_idx]
        else:
            # フォールバック
            fps = video_info.get('fps', 30)
            timestamp = frame_number / fps

        formatted.append({
            'frame': frame_number,
            'frame_number': frame_number,
            'timestamp': timestamp,
            'hands': frames_dict[frame_number]
        })

    logger.info(f"Formatted {len(formatted)} skeleton frames with hands data")
    return formatted


def format_instrument_data(
    raw_results: List[Dict],
    extraction_result: Optional[ExtractionResult],
    video_info: Dict[str, Any] = None,
) -> List[Dict]:
    """
    器具検出結果をフォーマット

    extraction_resultのframe_indicesとtimestampsを使用して正確なマッピング

    Args:
        raw_results: 器具検出の生結果リスト
        extraction_result: フレーム抽出結果（frame_indices, timestamps）
        video_info: 動画情報（fpsなど）。extraction_resultがない場合のフォールバック用。

    Returns:
        フォーマット済み器具データリスト
    """
    if video_info is None:
        video_info = {}

    formatted = []

    # extraction_resultがない場合のフォールバック
    if not extraction_result:
        logger.error("[ANALYSIS] extraction_result not available for instrument data, using fallback")
        fps = video_info.get('fps', 30)
        from app.core.config import settings
        target_fps = getattr(settings, 'FRAME_EXTRACTION_FPS', 15)
        frame_skip = max(1, int(fps / target_fps))

        for frame_idx, result in enumerate(raw_results):
            if not isinstance(result, dict):
                continue
            actual_frame_number = frame_idx * frame_skip
            timestamp = actual_frame_number / fps if fps > 0 else frame_idx / 30.0
            instruments = result.get('instruments', result.get('detections', []))
            formatted.append({
                'frame_number': actual_frame_number,
                'timestamp': timestamp,
                'detections': instruments
            })
        return formatted

    # 新しいロジック: extraction_resultを使用
    logger.info(f"[ANALYSIS] _format_instrument_data using extraction_result: "
               f"{len(extraction_result.frame_indices)} frame_indices")

    for frame_idx, result in enumerate(raw_results):
        if not isinstance(result, dict):
            logger.warning(f"[ANALYSIS] Skipping non-dict instrument result: type={type(result)}")
            continue

        if frame_idx >= len(extraction_result.frame_indices):
            logger.warning(f"[ANALYSIS] Instrument frame {frame_idx} exceeds extraction_result length")
            break

        # extraction_resultから正確な値を取得
        actual_frame_number = extraction_result.frame_indices[frame_idx]
        timestamp = extraction_result.timestamps[frame_idx]

        # SAM2 Video APIは'instruments'キー、SAMTrackerUnifiedは'detections'キーを使う
        instruments = result.get('instruments', result.get('detections', []))

        # デバッグ：最初と最後のフレームを確認
        if frame_idx == 0 or frame_idx >= 110:
            logger.info(f"[ANALYSIS] Instrument frame {frame_idx}: "
                      f"actual_frame={actual_frame_number}, "
                      f"timestamp={timestamp:.3f}s, "
                      f"instruments_count={len(instruments)}")

        formatted.append({
            'frame_number': actual_frame_number,
            'timestamp': timestamp,
            'detections': instruments
        })

    logger.info(f"Formatted {len(formatted)} instrument detections with correct timestamps")
    return formatted


def compress_instrument_data(instrument_data: List[Dict]) -> List[Dict]:
    """
    大容量の器具追跡データを圧縮

    maskデータを輪郭座標に変換し、500KB超過の場合はサンプリングで削減する。

    Args:
        instrument_data: 器具追跡データのリスト

    Returns:
        圧縮された器具追跡データ
    """
    if not instrument_data:
        return []

    total_frames = len(instrument_data)
    logger.info(f"[ANALYSIS] Compressing {total_frames} frames of instrument data")

    # デバッグ：最初のフレームの構造を確認
    if total_frames > 0:
        first_frame = instrument_data[0]
        logger.info(f"[ANALYSIS] Compression input - First frame keys: {list(first_frame.keys())}")
        detections_key = 'detections' if 'detections' in first_frame else 'instruments'
        det_count = len(first_frame.get(detections_key, []))
        logger.info(f"[ANALYSIS] Compression input - First frame {detections_key} count: {det_count}")
        if det_count > 0:
            first_det = first_frame[detections_key][0]
            logger.info(f"[ANALYSIS] Compression input - First detection keys: {list(first_det.keys())}")

    # maskデータを除去して圧縮
    compressed_data = []

    # デバッグ: 圧縮開始時のログ
    logger.warning(f"[CONTOUR_DEBUG] Starting compression, total frames: {len(instrument_data)}")

    for frame_idx, frame_data in enumerate(instrument_data):
        # _format_instrument_dataが使用するキー名に対応
        compressed_frame = {
            'frame_number': frame_data.get('frame_number'),
            'timestamp': frame_data.get('timestamp', 0.0),
            'detections': []
        }

        # SAM2 Video APIのデータ構造に対応
        detections = frame_data.get('detections', [])

        # デバッグ: 最初のフレームで必ずログ出力
        if frame_idx == 0:
            logger.warning(f"[CONTOUR_DEBUG] Frame 0 has {len(detections)} detections")

        for det_idx, det in enumerate(detections):
            # デバッグ: detectionの構造を確認（WARNINGレベルで確実に出力）
            if frame_idx == 0 and det_idx == 0:
                logger.warning(f"[CONTOUR_DEBUG] First detection keys: {list(det.keys())}")
                logger.warning(f"[CONTOUR_DEBUG] First detection has 'mask': {'mask' in det}")
                if 'mask' in det:
                    mask_data = det.get('mask')
                    logger.warning(f"[CONTOUR_DEBUG] Mask type: {type(mask_data)}, is None: {mask_data is None}")
                    if isinstance(mask_data, np.ndarray):
                        logger.warning(f"[CONTOUR_DEBUG] Mask shape: {mask_data.shape}, dtype: {mask_data.dtype}, sum: {mask_data.sum()}")

            compressed_det = {
                'id': det.get('id'),
                'name': det.get('name', ''),
                'center': det.get('center', []),
                'bbox': det.get('bbox', []),
                'confidence': det.get('confidence', 0.0),
                'contour': extract_mask_contour(det.get('mask'))
            }

            compressed_frame['detections'].append(compressed_det)

        compressed_data.append(compressed_frame)

    # 圧縮結果を確認
    frames_with_dets = sum(1 for f in compressed_data if len(f.get('detections', [])) > 0)
    logger.info(f"[ANALYSIS] After mask removal: {frames_with_dets}/{total_frames} frames have detections")

    # 500KB超過の場合、サンプリングで削減
    compressed_json = json.dumps(compressed_data)
    compressed_size = len(compressed_json)
    logger.info(f"[ANALYSIS] Compressed data size: {compressed_size} characters")

    if compressed_size > 500000:
        logger.warning(f"[ANALYSIS] Still too large ({compressed_size} chars), sampling frames...")
        summary_data = []

        # 最初の10フレーム
        summary_data.extend(compressed_data[:10])

        # 10フレームごとのサンプル
        for i in range(10, total_frames - 10, 10):
            summary_data.append(compressed_data[i])

        # 最後の10フレーム
        if total_frames > 20:
            summary_data.extend(compressed_data[-10:])

        sampled_frames_with_dets = sum(1 for f in summary_data if len(f.get('detections', [])) > 0)
        logger.info(f"[ANALYSIS] Sampled {len(summary_data)} frames from {total_frames} total")
        logger.info(f"[ANALYSIS] Sampled data: {sampled_frames_with_dets}/{len(summary_data)} frames have detections")
        return summary_data

    return compressed_data


def convert_video_api_result(
    tracking_result: Dict[str, Any],
    total_frames: int,
    extraction_result: Optional[ExtractionResult] = None,
) -> List[Dict[str, Any]]:
    """
    SAM2 Video APIの結果を既存フォーマット（フレーム単位）に変換

    Args:
        tracking_result: Video APIの結果
        total_frames: 抽出されたフレーム数
        extraction_result: フレーム抽出結果（frame_indicesマッピング用）

    Returns:
        フレーム単位の結果リスト
    """
    logger.info("[EXPERIMENTAL] Converting Video API result to frame-based format...")

    # フレームごとの結果を初期化
    frame_results = [
        {"detected": False, "instruments": []}
        for _ in range(total_frames)
    ]

    # 各器具の軌跡をフレーム単位に分配
    instruments_data = tracking_result.get("instruments", [])

    # extraction_resultがある場合、動画フレーム番号→抽出インデックスのマッピングを作成
    video_frame_to_extract_idx = {}
    if extraction_result:
        for idx, video_frame_num in enumerate(extraction_result.frame_indices):
            video_frame_to_extract_idx[video_frame_num] = idx
        logger.info(f"[EXPERIMENTAL] Created frame mapping: {len(video_frame_to_extract_idx)} video frames → extract indices")

    for inst_data in instruments_data:
        inst_id = inst_data["instrument_id"]
        inst_name = inst_data["name"]
        trajectory = inst_data["trajectory"]

        for point_idx, point in enumerate(trajectory):
            # SAM2 Video APIは動画内の実際のフレーム番号を返す
            video_frame_idx = point["frame_index"]

            # 抽出されたフレームのインデックスに変換
            if extraction_result and video_frame_idx in video_frame_to_extract_idx:
                extract_idx = video_frame_to_extract_idx[video_frame_idx]
            else:
                if point_idx < 5:
                    logger.info(f"[SKIP] Inst {inst_id}, Point {point_idx}: video_frame={video_frame_idx} not in extraction mapping, skipping")
                continue

            if 0 <= extract_idx < total_frames:
                frame_results[extract_idx]["detected"] = True
                frame_results[extract_idx]["instruments"].append({
                    "id": inst_id,
                    "name": inst_name,
                    "center": point["center"],
                    "bbox": point["bbox"],
                    "confidence": point["confidence"],
                    "mask": point.get("mask")
                })

    # 検出があったフレーム数をカウント
    detected_frames = sum(1 for fr in frame_results if fr["detected"])
    logger.info(f"[EXPERIMENTAL] Converted to frame-based format: {detected_frames}/{total_frames} frames with detections")

    return frame_results


def convert_instruments_format(instruments: List[Dict]) -> List[Dict]:
    """
    保存されたinstruments形式をSAMTrackerUnified用に変換

    Input: [{"name": str, "bbox": [x,y,w,h], "frame_number": int, "mask": str}]
    Output: [{"id": int, "name": str, "selection": {"type": "mask"|"box", "data": ...}, "color": str}]

    Args:
        instruments: 保存されたinstruments形式のリスト

    Returns:
        SAMTrackerUnified用に変換されたinstrumentsリスト
    """
    converted = []
    colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF"]

    for idx, inst in enumerate(instruments):
        # マスクデータがある場合は優先的に使用（最も正確）
        if "mask" in inst and inst["mask"]:
            logger.info(f"[ANALYSIS] Instrument {idx} using mask-based initialization")
            converted.append({
                "id": idx,
                "name": inst.get("name", f"Instrument {idx + 1}"),
                "selection": {
                    "type": "mask",
                    "data": inst["mask"]
                },
                "color": inst.get("color", colors[idx % len(colors)])
            })
        # マスクがない場合はbboxにフォールバック
        elif "bbox" in inst:
            x, y, w, h = inst["bbox"]
            bbox_xyxy = [x, y, x + w, y + h]
            logger.info(f"[ANALYSIS] Instrument {idx} using box-based initialization (fallback)")
            converted.append({
                "id": idx,
                "name": inst.get("name", f"Instrument {idx + 1}"),
                "selection": {
                    "type": "box",
                    "data": bbox_xyxy
                },
                "color": inst.get("color", colors[idx % len(colors)])
            })
        elif "selection" in inst and inst["selection"].get("type") == "box":
            # 既に変換済みの場合はそのまま使用
            bbox_xyxy = inst["selection"]["data"]
            logger.info(f"[ANALYSIS] Instrument {idx} using pre-converted box format")
            converted.append({
                "id": idx,
                "name": inst.get("name", f"Instrument {idx + 1}"),
                "selection": {
                    "type": "box",
                    "data": bbox_xyxy
                },
                "color": inst.get("color", colors[idx % len(colors)])
            })
        # pointsリストからbboxを計算
        elif "points" in inst and inst["points"]:
            points = inst["points"]
            if len(points) >= 2:
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                x_min, y_min = min(xs), min(ys)
                x_max, y_max = max(xs), max(ys)
                bbox_xyxy = [x_min, y_min, x_max, y_max]
                logger.info(f"[ANALYSIS] Instrument {idx} using points-to-box conversion ({len(points)} points)")
                converted.append({
                    "id": idx,
                    "name": inst.get("name", f"Instrument {idx + 1}"),
                    "selection": {
                        "type": "box",
                        "data": bbox_xyxy
                    },
                    "color": inst.get("color", colors[idx % len(colors)])
                })
            else:
                logger.warning(f"[ANALYSIS] Instrument {idx} has insufficient points ({len(points)})")
        else:
            logger.warning(f"[ANALYSIS] Instrument {idx} has no valid bbox, mask, or points, skipping")
            continue

    logger.info(f"[ANALYSIS] Converted {len(converted)} instruments from saved format to SAM format")
    return converted


def collect_tracking_stats(
    detector: Any,
    instrument_results: List[Dict],
    tracking_stats: Dict,
) -> Dict:
    """
    トラッキング統計を収集する（Phase 2.2）

    Args:
        detector: SAMTrackerUnifiedインスタンス
        instrument_results: 器具検出結果
        tracking_stats: 既存のtracking_stats辞書（更新される）

    Returns:
        更新されたtracking_stats辞書
    """
    try:
        # SAMTrackerUnifiedから統計情報を取得
        if hasattr(detector, 'get_tracking_stats'):
            tracker_stats = detector.get_tracking_stats()

            # 器具ごとの統計
            for inst_key, inst_stats in tracker_stats.get('instruments', {}).items():
                if inst_key not in tracking_stats:
                    tracking_stats[inst_key] = {}

                tracking_stats[inst_key]['max_lost_count'] = inst_stats.get('lost_frames', 0)
                tracking_stats[inst_key]['last_score'] = inst_stats.get('last_score', 0.0)
                tracking_stats[inst_key]['trajectory_length'] = inst_stats.get('trajectory_length', 0)

        # 再検出イベントをカウント
        re_detection_count = {}
        for frame_data in instrument_results:
            if isinstance(frame_data, dict):
                detections = frame_data.get('detections', [])
                for detection in detections:
                    if detection.get('redetected'):
                        track_id = detection.get('track_id', 0)
                        inst_key = f"instrument_{track_id}"

                        if inst_key not in re_detection_count:
                            re_detection_count[inst_key] = 0
                        re_detection_count[inst_key] += 1

        # 再検出カウントをtracking_statsに追加
        for inst_key, count in re_detection_count.items():
            if inst_key not in tracking_stats:
                tracking_stats[inst_key] = {}
            tracking_stats[inst_key]['re_detections'] = count

        # 総フレーム数と検出フレーム数
        total_frames = len(instrument_results)
        detected_frames = sum(
            1 for frame_data in instrument_results
            if isinstance(frame_data, dict) and len(frame_data.get('detections', [])) > 0
        )

        tracking_stats['summary'] = {
            'total_frames': total_frames,
            'detected_frames': detected_frames,
            'detection_rate': detected_frames / total_frames if total_frames > 0 else 0
        }

        logger.info(f"[ANALYSIS] Collected tracking stats: {list(tracking_stats.keys())}")

    except Exception as e:
        logger.warning(f"[ANALYSIS] Failed to collect tracking stats: {e}")

    return tracking_stats
