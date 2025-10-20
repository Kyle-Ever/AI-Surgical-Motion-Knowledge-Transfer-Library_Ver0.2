"""
一時フレームストレージ管理
SAM2 Video Predictor用にフレームをJPEG形式で一時保存
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class TemporaryFrameStorage:
    """一時フレームストレージ管理クラス

    SAM2 Video Predictorが要求するJPEGフォルダ形式でフレームを一時保存し、
    処理完了後に自動クリーンアップを行う。

    使用例:
        storage = TemporaryFrameStorage("analysis_abc123")
        try:
            jpeg_dir = storage.save_frames(frames, quality=95)
            # SAM2処理
            sam2.init_state(video_path=jpeg_dir)
            ...
        finally:
            storage.cleanup()
    """

    def __init__(
        self,
        analysis_id: str,
        base_dir: Optional[Path] = None
    ):
        """
        初期化

        Args:
            analysis_id: 解析ID（フォルダ名として使用）
            base_dir: ベースディレクトリ（デフォルト: backend/temp_frames）
        """
        if base_dir is None:
            # デフォルト: backendディレクトリ配下のtemp_frames
            backend_dir = Path(__file__).parent.parent.parent
            base_dir = backend_dir / "temp_frames"

        self.base_dir = Path(base_dir)
        self.analysis_id = analysis_id
        self.temp_dir = self.base_dir / analysis_id
        self.created = False

    def save_frames(
        self,
        frames: List[np.ndarray],
        quality: int = 95,
        parallel: bool = True,
        max_workers: int = 4
    ) -> Path:
        """フレームをJPEG形式で保存

        Args:
            frames: フレーム配列のリスト
            quality: JPEG品質（1-100、デフォルト95）
            parallel: 並列処理を有効化（デフォルトTrue）
            max_workers: 並列処理のワーカー数（デフォルト4）

        Returns:
            JPEGフォルダのパス

        Raises:
            IOError: ディスク書き込みエラー
            ValueError: フレームが空
        """
        if not frames or len(frames) == 0:
            raise ValueError("Frames list is empty")

        # ディレクトリ作成
        try:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            self.created = True
            logger.info(f"Created temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Failed to create directory {self.temp_dir}: {e}")
            raise IOError(f"Cannot create temporary directory: {e}")

        # JPEG保存
        total_frames = len(frames)
        logger.info(f"Saving {total_frames} frames as JPEG (quality={quality}, parallel={parallel})")

        if parallel and total_frames > 10:
            # 並列保存（10フレーム以上の場合）
            self._save_frames_parallel(frames, quality, max_workers)
        else:
            # 順次保存
            self._save_frames_sequential(frames, quality)

        logger.info(f"Successfully saved {total_frames} frames to {self.temp_dir}")
        return self.temp_dir

    def _save_frames_sequential(
        self,
        frames: List[np.ndarray],
        quality: int
    ) -> None:
        """順次保存"""
        for idx, frame in enumerate(frames):
            jpeg_path = self.temp_dir / f"{idx:05d}.jpg"
            success = cv2.imwrite(
                str(jpeg_path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, quality]
            )
            if not success:
                raise IOError(f"Failed to write frame {idx} to {jpeg_path}")

    def _save_frames_parallel(
        self,
        frames: List[np.ndarray],
        quality: int,
        max_workers: int
    ) -> None:
        """並列保存"""
        def save_single_frame(idx_frame):
            idx, frame = idx_frame
            jpeg_path = self.temp_dir / f"{idx:05d}.jpg"
            success = cv2.imwrite(
                str(jpeg_path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, quality]
            )
            if not success:
                raise IOError(f"Failed to write frame {idx} to {jpeg_path}")
            return idx

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(save_single_frame, enumerate(frames)))

        logger.debug(f"Parallel save completed: {len(results)} frames")

    def cleanup(self, ignore_errors: bool = True) -> bool:
        """一時フォルダを削除

        Args:
            ignore_errors: エラーを無視（デフォルトTrue）

        Returns:
            削除成功時True
        """
        if not self.created:
            logger.debug(f"Temporary directory was not created, skipping cleanup")
            return True

        if not self.temp_dir.exists():
            logger.debug(f"Temporary directory already deleted: {self.temp_dir}")
            return True

        try:
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
            self.created = False
            return True
        except Exception as e:
            msg = f"Failed to cleanup temporary directory {self.temp_dir}: {e}"
            if ignore_errors:
                logger.warning(msg)
                return False
            else:
                logger.error(msg)
                raise IOError(msg)

    def get_frame_count(self) -> int:
        """保存されたフレーム数を取得

        Returns:
            JPEGファイル数
        """
        if not self.temp_dir.exists():
            return 0

        jpeg_files = list(self.temp_dir.glob("*.jpg"))
        return len(jpeg_files)

    def get_total_size_mb(self) -> float:
        """保存されたファイルの合計サイズを取得

        Returns:
            合計サイズ（MB）
        """
        if not self.temp_dir.exists():
            return 0.0

        total_bytes = sum(f.stat().st_size for f in self.temp_dir.glob("*.jpg"))
        return total_bytes / (1024 * 1024)

    def __enter__(self):
        """コンテキストマネージャ: with文対応"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャ: 自動クリーンアップ"""
        self.cleanup(ignore_errors=True)
        return False  # 例外を再送出

    def __del__(self):
        """デストラクタ: 念のためクリーンアップ"""
        if self.created:
            self.cleanup(ignore_errors=True)


def cleanup_old_temp_frames(
    base_dir: Optional[Path] = None,
    max_age_hours: int = 24
) -> int:
    """古い一時フォルダを削除

    定期的に実行して、残存する古い一時フォルダをクリーンアップ

    Args:
        base_dir: ベースディレクトリ（デフォルト: backend/temp_frames）
        max_age_hours: 削除対象の最大経過時間（時間）

    Returns:
        削除したフォルダ数
    """
    if base_dir is None:
        backend_dir = Path(__file__).parent.parent.parent
        base_dir = backend_dir / "temp_frames"

    base_dir = Path(base_dir)

    if not base_dir.exists():
        return 0

    import time
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0

    for analysis_dir in base_dir.iterdir():
        if not analysis_dir.is_dir():
            continue

        # ディレクトリの作成時刻をチェック
        dir_age = now - analysis_dir.stat().st_mtime

        if dir_age > max_age_seconds:
            try:
                shutil.rmtree(analysis_dir)
                logger.info(f"Deleted old temporary directory: {analysis_dir} (age: {dir_age/3600:.1f}h)")
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete old directory {analysis_dir}: {e}")

    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} old temporary directories")

    return deleted_count
