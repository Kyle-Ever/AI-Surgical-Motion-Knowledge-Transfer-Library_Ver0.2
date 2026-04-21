"""
Review Deck 向けの気づきイベント検出器 (v0.3-chunk)。

設計思想:
- 実習生へのフィードバック単位は「短い手技の区切り」である
- 窓ごとの偏差判定は同じ現象を何度も発火するため避け、
  チャンク単位で最悪の指標 1 つだけ代表させ、かつ隣接マージする
- 閾値は固定値ではなく動画内の相対値 (中央値・百分位数) で決める
- 25 秒動画で 3〜8 件、上限は 15 件程度に収める

処理フロー:
  1. preprocess で速度・位置の時系列を作る
  2. 両手停止区間 (B1) を抽出 → そのまま event 化
  3. 動画を固定長 (chunk_sec=3秒) のチャンクで分割
  4. 各チャンクで A1/A2/A3/B2/B3 の値を計算
  5. 動画全体の中央値/分布で各チャンク値を相対評価し severity を決める
  6. 1 チャンクに複数指標が悪い場合は最も severity の強いもの 1 つだけ採用
  7. 隣接する「同じ指標 × 同じ severity」のチャンクを 1 イベントにマージ
  8. 指標ごとに上限 5 件、全体 15 件に絞って返す
  9. 各イベントに coaching (fact/why/action) テンプレを付与
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial import ConvexHull

from .metrics_config import MetricsConfigManager
from .preprocessor import preprocess_skeleton_data
from .types import PreprocessedData
from .waste_detector import WasteDetector

logger = logging.getLogger(__name__)


INDICATOR_LABELS = {
    "A1": "動作経済性",
    "A2": "動作滑らかさ",
    "A3": "両手協調性",
    "B1": "ロスタイム",
    "B2": "動作回数効率",
    "B3": "作業空間偏差",
}

INDICATOR_CATEGORIES = {
    "A1": "motion_quality",
    "A2": "motion_quality",
    "A3": "motion_quality",
    "B1": "waste_detection",
    "B2": "waste_detection",
    "B3": "waste_detection",
}

SEVERITY_ORDER = {"normal": 0, "notable": 1, "hot": 2}


@dataclass
class _Chunk:
    """固定長チャンク"""
    idx: int
    start_idx: int
    end_idx: int
    start_sec: float
    end_sec: float

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


@dataclass
class _ChunkMetrics:
    """1 チャンクにおける各指標の計算値"""
    path_per_sec: Optional[float] = None
    sparc: Optional[float] = None
    correlation: Optional[float] = None
    movements_per_min: Optional[float] = None
    hull_area: Optional[float] = None


@dataclass
class _ChunkVerdict:
    """1 チャンクに対する severity 判定 (1 指標のみ代表)"""
    indicator: Optional[str] = None
    severity: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class EventDetector:
    """6指標それぞれの気づきポイントをチャンク単位で抽出する post-processor"""

    def __init__(self, fps: float = 30.0):
        cfg = MetricsConfigManager().get_config()
        self._cfg = cfg
        e = cfg.get("event_detection", {})
        self.version = e.get("version", "v0.3-chunk")
        self.chunk_sec = float(e.get("chunk_sec", 3.0))
        self.a1_notable = float(e.get("a1_path_median_ratio_notable", 1.3))
        self.a1_hot = float(e.get("a1_path_median_ratio_hot", 1.7))
        self.a2_notable_pct = float(e.get("a2_sparc_percentile_notable", 25))
        self.a2_hot_pct = float(e.get("a2_sparc_percentile_hot", 10))
        self.a3_notable = float(e.get("a3_low_corr_notable", 0.2))
        self.a3_hot = float(e.get("a3_low_corr_hot", 0.0))
        self.b1_notable_sec = float(e.get("b1_notable_min_sec", 3.0))
        self.b1_hot_sec = float(e.get("b1_hot_min_sec", 8.0))
        self.b2_notable = float(e.get("b2_mpm_median_ratio_notable", 1.3))
        self.b2_hot = float(e.get("b2_mpm_median_ratio_hot", 1.7))
        self.b3_notable = float(e.get("b3_hull_median_ratio_notable", 1.5))
        self.b3_hot = float(e.get("b3_hull_median_ratio_hot", 2.0))
        self.merge_adjacent = bool(e.get("merge_adjacent", True))
        self.max_events = int(e.get("max_events_per_analysis", 15))
        self.max_per_indicator = int(e.get("max_per_indicator", 5))

        self.fps = fps
        self._waste = WasteDetector(fps=fps, config=cfg)

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def detect(
        self,
        analysis_id: str,
        skeleton_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not skeleton_data or len(skeleton_data) < 10:
            logger.info("[EVENT_DETECTOR v0.3] skeleton_data too small, skip")
            return []

        data = preprocess_skeleton_data(skeleton_data, self.fps)
        duration = data.total_duration_seconds
        if duration <= 0:
            return []

        events: List[Dict[str, Any]] = []

        # --- 1. B1: ロスタイム (変更なし) ---
        events.extend(self._b1_events(analysis_id, data))

        # --- 2. 固定長チャンクに分割 ---
        chunks = self._chunks(data)
        if chunks:
            chunk_metrics = [self._compute_chunk_metrics(data, c) for c in chunks]
            g = self._global_stats(chunk_metrics)
            verdicts = [
                self._verdict_for_chunk(m, g) for m in chunk_metrics
            ]
            logger.info(
                "[EVENT_DETECTOR v0.3] %s: %d chunks, %d with verdict",
                analysis_id, len(chunks),
                sum(1 for v in verdicts if v.indicator is not None),
            )

            # --- 3. 隣接する同一 (indicator, severity) の chunk をマージ ---
            events.extend(
                self._build_events_from_verdicts(analysis_id, chunks, verdicts)
            )

        # --- 4. 件数キャップ ---
        events = self._cap_events(events)

        # --- 5. coaching 文の付与 ---
        for ev in events:
            self._fill_coaching(ev)

        events.sort(key=lambda e: (e["timestamp"], e["indicator"]))
        logger.info(
            "[EVENT_DETECTOR v0.3] %s: %d events (duration=%.1fs, version=%s)",
            analysis_id, len(events), duration, self.version,
        )
        return events

    # ------------------------------------------------------------------
    # B1: 既存 lost_time_segments を event 化
    # ------------------------------------------------------------------

    def _b1_events(
        self, analysis_id: str, data: PreprocessedData
    ) -> List[Dict[str, Any]]:
        raw = self._waste.lost_time(data)
        segments = raw.get("lost_time_segments", []) or []
        events: List[Dict[str, Any]] = []
        for i, seg in enumerate(segments):
            dur = float(seg.get("duration_seconds", 0.0))
            ts = float(seg.get("start_time", 0.0))
            if dur < self.b1_notable_sec:
                continue
            sev = "hot" if dur >= self.b1_hot_sec else "notable"
            events.append(
                self._mk_event(
                    analysis_id=analysis_id,
                    indicator="B1",
                    seq=i,
                    timestamp=ts,
                    duration=dur,
                    severity=sev,
                    title=f"両手停止 {dur:.1f}秒",
                    extra={"stop_seconds": dur},
                )
            )
        return events

    # ------------------------------------------------------------------
    # 固定長チャンクの生成
    # ------------------------------------------------------------------

    def _chunks(self, data: PreprocessedData) -> List[_Chunk]:
        fps = data.fps if data.fps > 0 else 30.0
        n = data.total_frames
        if n == 0:
            return []
        chunk_frames = max(int(round(self.chunk_sec * fps)), 5)

        chunks: List[_Chunk] = []
        i = 0
        idx = 0
        while i < n:
            end = min(i + chunk_frames, n)
            # 最後の端数チャンクが非常に短いときは前のチャンクに吸収
            if end - i < chunk_frames * 0.5 and chunks:
                last = chunks[-1]
                chunks[-1] = _Chunk(
                    idx=last.idx,
                    start_idx=last.start_idx, end_idx=end,
                    start_sec=last.start_sec, end_sec=end / fps,
                )
                break
            chunks.append(_Chunk(
                idx=idx, start_idx=i, end_idx=end,
                start_sec=i / fps, end_sec=end / fps,
            ))
            idx += 1
            i = end
        return chunks

    # ------------------------------------------------------------------
    # チャンク内指標の計算
    # ------------------------------------------------------------------

    def _compute_chunk_metrics(
        self, data: PreprocessedData, c: _Chunk
    ) -> _ChunkMetrics:
        s, e = c.start_idx, c.end_idx
        dur = c.duration_sec
        m = _ChunkMetrics()
        if dur <= 0:
            return m

        fps = data.fps if data.fps > 0 else 30.0

        # A1: path/sec (両手合算)
        lp = _path_length(data.left_positions[s:e])
        rp = _path_length(data.right_positions[s:e])
        m.path_per_sec = (lp + rp) / dur

        # A2: SPARC (区間内の combined 速度)
        vels = []
        for l, r in zip(data.left_velocities[s:e], data.right_velocities[s:e]):
            if l is not None and r is not None:
                vels.append((l + r) / 2.0)
            elif l is not None:
                vels.append(l)
            elif r is not None:
                vels.append(r)
        if len(vels) >= 4:
            m.sparc = _sparc(vels, fps)

        # A3: 両手速度相関
        pairs = [
            (l, r) for l, r in zip(data.left_velocities[s:e], data.right_velocities[s:e])
            if l is not None and r is not None
        ]
        if len(pairs) >= 5:
            la = np.array([p[0] for p in pairs])
            ra = np.array([p[1] for p in pairs])
            if np.std(la) >= 1e-6 and np.std(ra) >= 1e-6:
                c_val = np.corrcoef(la, ra)[0, 1]
                m.correlation = float(c_val) if not np.isnan(c_val) else None

        # B2: movements_per_min
        combined_vels = [v for v in data.combined_velocities[s:e] if v is not None]
        if len(combined_vels) >= 5:
            threshold = self._waste.move_vel_px if data.is_pixel_coords else self._waste.move_vel
            threshold_low = threshold * self._waste.hysteresis_ratio
            count = 0
            in_movement = combined_vels[0] >= threshold
            for v in combined_vels[1:]:
                if in_movement:
                    if v < threshold_low:
                        in_movement = False
                else:
                    if v >= threshold:
                        count += 1
                        in_movement = True
            m.movements_per_min = count / dur * 60.0

        # B3: 凸包面積
        pts: List[List[float]] = []
        for p in data.left_positions[s:e]:
            if p:
                pts.append([p["x"], p["y"]])
        for p in data.right_positions[s:e]:
            if p:
                pts.append([p["x"], p["y"]])
        if len(pts) >= 4:
            try:
                m.hull_area = float(ConvexHull(np.unique(np.array(pts), axis=0)).volume)
            except Exception:
                m.hull_area = None

        return m

    # ------------------------------------------------------------------
    # 全体統計
    # ------------------------------------------------------------------

    def _global_stats(self, cms: List[_ChunkMetrics]) -> Dict[str, Optional[float]]:
        path = [m.path_per_sec for m in cms if m.path_per_sec is not None]
        sparc = [m.sparc for m in cms if m.sparc is not None]
        mpm = [m.movements_per_min for m in cms if m.movements_per_min is not None]
        hull = [m.hull_area for m in cms if m.hull_area is not None]

        def _median(xs): return float(np.median(xs)) if xs else None
        def _pct(xs, q): return float(np.percentile(xs, q)) if xs else None

        return {
            "path_median": _median(path),
            "sparc_p_notable": _pct(sparc, self.a2_notable_pct) if sparc else None,
            "sparc_p_hot": _pct(sparc, self.a2_hot_pct) if sparc else None,
            "mpm_median": _median(mpm),
            "hull_median": _median(hull),
        }

    # ------------------------------------------------------------------
    # チャンクの verdict (最悪 1 指標の選択)
    # ------------------------------------------------------------------

    def _verdict_for_chunk(
        self, m: _ChunkMetrics, g: Dict[str, Optional[float]]
    ) -> _ChunkVerdict:
        candidates: List[Tuple[str, str, Dict[str, Any]]] = []

        if m.path_per_sec is not None and g["path_median"] and g["path_median"] > 0:
            r = m.path_per_sec / g["path_median"]
            if r >= self.a1_hot:
                candidates.append(("A1", "hot", {"ratio": r}))
            elif r >= self.a1_notable:
                candidates.append(("A1", "notable", {"ratio": r}))

        if m.sparc is not None and g["sparc_p_notable"] is not None:
            if g["sparc_p_hot"] is not None and m.sparc <= g["sparc_p_hot"]:
                candidates.append(("A2", "hot", {"sparc": m.sparc}))
            elif m.sparc <= g["sparc_p_notable"]:
                candidates.append(("A2", "notable", {"sparc": m.sparc}))

        if m.correlation is not None:
            if m.correlation <= self.a3_hot:
                candidates.append(("A3", "hot", {"correlation": m.correlation}))
            elif m.correlation <= self.a3_notable:
                candidates.append(("A3", "notable", {"correlation": m.correlation}))

        if m.movements_per_min is not None and g["mpm_median"] and g["mpm_median"] > 0:
            r = m.movements_per_min / g["mpm_median"]
            if r >= self.b2_hot:
                candidates.append(("B2", "hot", {"ratio": r}))
            elif r >= self.b2_notable:
                candidates.append(("B2", "notable", {"ratio": r}))

        if m.hull_area is not None and g["hull_median"] and g["hull_median"] > 0:
            r = m.hull_area / g["hull_median"]
            if r >= self.b3_hot:
                candidates.append(("B3", "hot", {"ratio": r}))
            elif r >= self.b3_notable:
                candidates.append(("B3", "notable", {"ratio": r}))

        if not candidates:
            return _ChunkVerdict()

        candidates.sort(key=lambda c: (-SEVERITY_ORDER[c[1]], c[0]))
        ind, sev, extra = candidates[0]
        return _ChunkVerdict(indicator=ind, severity=sev, extra=extra)

    # ------------------------------------------------------------------
    # 隣接マージしてイベント化
    # ------------------------------------------------------------------

    def _build_events_from_verdicts(
        self,
        analysis_id: str,
        chunks: List[_Chunk],
        verdicts: List[_ChunkVerdict],
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        i = 0
        seq = 0
        while i < len(chunks):
            v = verdicts[i]
            if v.indicator is None:
                i += 1
                continue

            # 同じ (indicator, severity) が連続する範囲を吸収
            j = i + 1
            if self.merge_adjacent:
                while (
                    j < len(chunks)
                    and verdicts[j].indicator == v.indicator
                    and verdicts[j].severity == v.severity
                ):
                    j += 1

            start_sec = chunks[i].start_sec
            end_sec = chunks[j - 1].end_sec
            dur = end_sec - start_sec
            extra = dict(v.extra or {})
            # マージ範囲の代表値 (最悪値) を格納したいので、j 範囲で再走査
            # 簡易: 最初のチャンクの extra をそのまま使う
            title = self._title_for(v.indicator, extra)

            events.append(
                self._mk_event(
                    analysis_id=analysis_id,
                    indicator=v.indicator,
                    seq=seq,
                    timestamp=start_sec,
                    duration=dur,
                    severity=v.severity,
                    title=title,
                    extra=extra,
                )
            )
            seq += 1
            i = j
        return events

    @staticmethod
    def _title_for(indicator: str, extra: Dict[str, Any]) -> str:
        if indicator == "A1":
            r = extra.get("ratio", 1.0)
            return f"移動距離過多 × {r:.1f}"
        if indicator == "A2":
            s = extra.get("sparc", 0.0)
            return f"滑らかさ低下 SPARC={s:.2f}"
        if indicator == "A3":
            c = extra.get("correlation", 0.0)
            return f"両手協調の乱れ r={c:.2f}"
        if indicator == "B2":
            r = extra.get("ratio", 1.0)
            return f"動作回数過多 × {r:.1f}"
        if indicator == "B3":
            r = extra.get("ratio", 1.0)
            return f"作業範囲の逸脱 × {r:.1f}"
        return ""

    # ------------------------------------------------------------------
    # 件数キャップ
    # ------------------------------------------------------------------

    def _cap_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_ind: Dict[str, List[Dict[str, Any]]] = {}
        for ev in events:
            by_ind.setdefault(ev["indicator"], []).append(ev)
        kept: List[Dict[str, Any]] = []
        for ind, evs in by_ind.items():
            evs.sort(key=lambda e: (-SEVERITY_ORDER[e["severity"]], e["timestamp"]))
            kept.extend(evs[: self.max_per_indicator])

        kept.sort(key=lambda e: (-SEVERITY_ORDER[e["severity"]], e["timestamp"]))
        return kept[: self.max_events]

    # ------------------------------------------------------------------
    # coaching テンプレ
    # ------------------------------------------------------------------

    _COACHING_TEMPLATES = {
        "A1": {
            "why": "手の移動距離が長いのは、目的位置の決定に迷いがあるか、"
                    "無駄な寄り道が混ざっていることを示します。",
            "action": "次に触れる位置を先に決めてから手を動かす習慣をつけると、"
                        "移動距離が自然に短くなります。",
        },
        "A2": {
            "why": "動きがぎこちないときは、小刻みな修正や微調整が多発しています。"
                    "器具先端の目的位置のイメージが曖昧な時に起きやすい兆候です。",
            "action": "一動作を一気に行い切るつもりで、途中で迷わない動作計画を意識してみましょう。",
        },
        "A3": {
            "why": "両手の速度がかみ合っていない場合、片手の動きに引きずられて"
                    "もう一方の保持が乱れている可能性があります。",
            "action": "非利き手を「支え続ける役」と明確に意識すると、左右の連動が安定します。",
        },
        "B1": {
            "why": "手術動画における3秒を超える両手停止は、"
                    "次の手順への躊躇・計画の見直し・想定外の事象の可能性があります。",
            "action": "道具を持つ前に次の動作を頭の中でなぞる習慣をつけると、"
                        "長い停止を減らせます。",
        },
        "B2": {
            "why": "動作回数が多いのは、一動作で済むべきところを複数回に分けてしまっている兆候です。"
                    "迷いや修正の表れでもあります。",
            "action": "狙った位置を一発で決めるつもりで、動作の開始前に少し間を取ってみましょう。",
        },
        "B3": {
            "why": "手が広い範囲に散らばるのは、術野から意識が外れる瞬間がある可能性を示します。"
                    "器具の持ち替えや視線移動が頻繁になっているかもしれません。",
            "action": "術野の中心を意識し、手の可動域を必要最小限に保つよう心掛けましょう。",
        },
    }

    def _fill_coaching(self, ev: Dict[str, Any]) -> None:
        ind = ev["indicator"]
        ts = ev["timestamp"]
        dur = ev.get("duration")
        extra = ev.pop("_extra", {}) or {}

        ts_label = _format_time(ts)
        end_label = _format_time(ts + (dur or 0.0))

        if ind == "B1":
            fact = f"{ts_label}〜{end_label} の{dur:.1f}秒間、両手が停止しています。"
        elif ind == "A1":
            r = extra.get("ratio")
            ratio_txt = f"（動画平均の{r:.1f}倍）" if r else ""
            fact = f"{ts_label}からの{dur:.1f}秒間、手の移動距離が増えています{ratio_txt}。"
        elif ind == "A2":
            sparc = extra.get("sparc")
            sparc_txt = f"（SPARC {sparc:.2f}）" if sparc is not None else ""
            fact = f"{ts_label}からの{dur:.1f}秒間、手の動きがぎこちなくなっています{sparc_txt}。"
        elif ind == "A3":
            corr = extra.get("correlation")
            corr_txt = f"（相関 {corr:.2f}）" if corr is not None else ""
            fact = f"{ts_label}からの{dur:.1f}秒間、左右の手の連動が乱れています{corr_txt}。"
        elif ind == "B2":
            r = extra.get("ratio")
            ratio_txt = f"（動画平均の{r:.1f}倍）" if r else ""
            fact = f"{ts_label}からの{dur:.1f}秒間、細かい動作が増えています{ratio_txt}。"
        elif ind == "B3":
            r = extra.get("ratio")
            ratio_txt = f"（動画平均の{r:.1f}倍）" if r else ""
            fact = f"{ts_label}からの{dur:.1f}秒間、手の可動域が広がっています{ratio_txt}。"
        else:
            fact = ""

        tmpl = self._COACHING_TEMPLATES.get(ind, {"why": "", "action": ""})
        ev["coaching_fact"] = fact
        ev["coaching_why"] = tmpl.get("why", "")
        ev["coaching_action"] = tmpl.get("action", "")
        ev["description"] = "\n".join(
            filter(None, [fact, tmpl.get("why", ""), tmpl.get("action", "")])
        )

    # ------------------------------------------------------------------
    # 共通ユーティリティ
    # ------------------------------------------------------------------

    def _mk_event(
        self,
        *,
        analysis_id: str,
        indicator: str,
        seq: int,
        timestamp: float,
        duration: Optional[float],
        severity: str,
        title: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "id": f"{analysis_id}:{indicator}:{seq:04d}",
            "timestamp": round(float(timestamp), 3),
            "duration": round(float(duration), 3) if duration is not None else None,
            "indicator": indicator,
            "category": INDICATOR_CATEGORIES[indicator],
            "severity": severity,
            "title": title,
            "description": "",
            "coaching_fact": "",
            "coaching_why": "",
            "coaching_action": "",
            "related_event_ids": [],
            "_extra": extra or {},
        }


# ==========================================================================
# ヘルパー
# ==========================================================================

def _path_length(positions: List[Optional[Dict[str, float]]]) -> float:
    total = 0.0
    prev = None
    for p in positions:
        if p is not None and prev is not None:
            dx = p["x"] - prev["x"]
            dy = p["y"] - prev["y"]
            total += math.sqrt(dx * dx + dy * dy)
        if p is not None:
            prev = p
    return total


def _sparc(velocities: List[float], fps: float) -> Optional[float]:
    arr = np.asarray(velocities, dtype=float)
    if arr.size < 4:
        return None
    if arr.size > 20:
        p99 = np.percentile(arr, 99)
        arr = np.clip(arr, 0, p99)
    peak = np.max(np.abs(arr))
    if peak < 1e-9:
        return -7.0
    norm = arr / peak
    N = len(norm)
    V = np.fft.rfft(norm)
    freqs = np.fft.rfftfreq(N, d=1.0 / fps)
    mag = np.abs(V)
    if mag[0] > 0:
        mag = mag / mag[0]
    mask = freqs <= 20.0
    fm = freqs[mask]
    vm = mag[mask]
    if len(fm) < 2:
        return -7.0
    dfreq = np.diff(fm)
    dv = np.diff(vm)
    return -float(np.sum(np.sqrt(dfreq ** 2 + dv ** 2)))


def _format_time(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}:{s:02d}"
