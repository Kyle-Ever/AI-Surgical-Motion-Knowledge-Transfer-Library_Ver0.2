"""
Unit tests for EventDetector v0.2-segment (区間ベース検出器)

テスト観点:
1. 空/極小 skeleton_data では [] を返す (fail-soft)
2. 長い両手停止 → B1 hot イベントが生成される
3. 返り値がすべて ReviewEvent スキーマを満たし coaching 文が付く
4. 動画全体で上限 15 件、指標あたり上限 5 件を超えない
5. 穏やかな動作では過剰なイベントが出ない
6. 動作区間が短すぎる (< 1.5s) ものはイベント対象外
"""

from __future__ import annotations

import math
from typing import Dict, List

import pytest

from app.schemas.review_event import ReviewEvent
from app.services.metrics.event_detector import EventDetector


FPS = 15.0


def _frame(i: int, left_xy=None, right_xy=None) -> Dict:
    hands = []
    if left_xy is not None:
        hands.append({
            "hand_type": "Left",
            "landmarks": {"point_0": {"x": float(left_xy[0]), "y": float(left_xy[1])}},
        })
    if right_xy is not None:
        hands.append({
            "hand_type": "Right",
            "landmarks": {"point_0": {"x": float(right_xy[0]), "y": float(right_xy[1])}},
        })
    return {
        "frame_number": i,
        "timestamp": round(i / FPS, 3),
        "hands": hands,
    }


def _build_steady_skeleton(seconds: float) -> List[Dict]:
    """両手が sine 軌道で継続的に動く skeleton_data"""
    total_frames = int(seconds * FPS)
    frames = []
    for i in range(total_frames):
        t = i / FPS
        lx = 100.0 + 30.0 * math.sin(t * 0.8)
        ly = 200.0 + 15.0 * math.cos(t * 0.6)
        rx = 400.0 + 30.0 * math.sin(t * 0.8 + 0.3)
        ry = 200.0 + 15.0 * math.cos(t * 0.6 + 0.3)
        frames.append(_frame(i, (lx, ly), (rx, ry)))
    return frames


def _inject_both_hands_stop(frames: List[Dict], start_sec: float, dur_sec: float) -> None:
    start_f = int(start_sec * FPS)
    end_f = int((start_sec + dur_sec) * FPS)
    if start_f <= 0 or end_f >= len(frames):
        return
    anchor = frames[start_f - 1]
    left = anchor["hands"][0]["landmarks"]["point_0"]
    right = anchor["hands"][1]["landmarks"]["point_0"]
    for i in range(start_f, end_f):
        frames[i]["hands"][0]["landmarks"]["point_0"] = {"x": left["x"], "y": left["y"]}
        frames[i]["hands"][1]["landmarks"]["point_0"] = {"x": right["x"], "y": right["y"]}


def _inject_jerky_burst(frames: List[Dict], start_sec: float, dur_sec: float) -> None:
    """指定区間で急激な往復動作を注入 (A1/A2/B2 のトリガー用)"""
    start_f = int(start_sec * FPS)
    end_f = int((start_sec + dur_sec) * FPS)
    for i in range(start_f, min(end_f, len(frames))):
        off = 80.0 if i % 2 == 0 else -80.0
        frames[i]["hands"][0]["landmarks"]["point_0"]["x"] += off
        frames[i]["hands"][1]["landmarks"]["point_0"]["x"] -= off


class TestEventDetectorBasics:
    def test_empty_data_returns_empty(self):
        assert EventDetector(fps=FPS).detect("a1", []) == []

    def test_too_small_data_returns_empty(self):
        frames = _build_steady_skeleton(0.3)
        assert EventDetector(fps=FPS).detect("a1", frames) == []


class TestLostTimeEvent:
    def test_long_both_hands_stop_generates_hot_b1(self):
        frames = _build_steady_skeleton(30.0)
        _inject_both_hands_stop(frames, start_sec=10.0, dur_sec=10.0)
        events = EventDetector(fps=FPS).detect("testA", frames)
        b1 = [e for e in events if e["indicator"] == "B1"]
        assert b1, "B1 event should be detected"
        hot = [e for e in b1 if e["severity"] == "hot"]
        assert hot, "B1 hot expected for 10s stop"
        ev = hot[0]
        assert abs(ev["timestamp"] - 10.0) < 0.5
        assert ev["duration"] is not None and ev["duration"] >= 8.0
        assert "両手停止" in ev["title"]


class TestSchemaAndCoaching:
    def test_all_events_validate_with_coaching_filled(self):
        frames = _build_steady_skeleton(25.0)
        _inject_both_hands_stop(frames, start_sec=5.0, dur_sec=5.0)
        _inject_jerky_burst(frames, start_sec=15.0, dur_sec=4.0)
        events = EventDetector(fps=FPS).detect("x", frames)
        assert events, "at least one event expected"
        for raw in events:
            ev = ReviewEvent.model_validate(raw)
            assert ev.id.startswith("x:")
            assert ev.indicator in {"A1", "A2", "A3", "B1", "B2", "B3"}
            assert ev.severity in {"normal", "notable", "hot"}
            # coaching 3 段が埋まっていること
            assert ev.coaching_fact, f"fact empty: {ev.id}"
            assert ev.coaching_why, f"why empty: {ev.id}"
            assert ev.coaching_action, f"action empty: {ev.id}"


class TestEventCap:
    def test_total_and_per_indicator_cap(self):
        """激しい合成動画で必ず上限 15 / 指標あたり 5 を満たす"""
        frames = _build_steady_skeleton(60.0)
        # 複数箇所にジャーキーバーストを注入
        for t in [5.0, 12.0, 20.0, 28.0, 36.0, 44.0, 52.0]:
            _inject_jerky_burst(frames, start_sec=t, dur_sec=3.0)
        events = EventDetector(fps=FPS).detect("cap", frames)
        assert len(events) <= 15, f"total cap violated: {len(events)}"
        from collections import Counter
        per_ind = Counter(e["indicator"] for e in events)
        for ind, n in per_ind.items():
            assert n <= 5, f"per-indicator cap violated for {ind}: {n}"


class TestSmokeSteady:
    def test_steady_motion_produces_few_events(self):
        frames = _build_steady_skeleton(25.0)
        events = EventDetector(fps=FPS).detect("steady", frames)
        # 穏やかな動きだけなら B1 は出ず、全体も 8 件以下におさまる想定
        assert not any(e["indicator"] == "B1" for e in events)
        assert len(events) <= 8, f"expected few events, got {len(events)}"
