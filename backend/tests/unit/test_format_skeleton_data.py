"""
ユニットテスト: _format_skeleton_data()メソッド

Fail Fast原則の検証:
- frame_indexが存在する場合: 正常にフォーマット
- frame_indexが欠損している場合: ValueErrorを発生
"""

import pytest
from app.services.analysis_service_v2 import AnalysisServiceV2


class TestFormatSkeletonData:
    """骨格データフォーマット関数のユニットテスト"""

    def setup_method(self):
        """テストセットアップ"""
        self.service = AnalysisServiceV2()
        # ビデオ情報を設定
        self.service.video_info = {'fps': 30}

    def test_format_with_frame_index(self):
        """正常系: frame_indexが存在する場合"""
        raw_results = [
            {
                'detected': True,
                'frame_index': 0,
                'hands': [
                    {
                        'hand_type': 'Left',
                        'landmarks': {'0': {'x': 0.5, 'y': 0.5}},
                        'palm_center': {'x': 0.5, 'y': 0.5},
                        'finger_angles': {},
                        'hand_openness': 0.8
                    }
                ]
            },
            {
                'detected': True,
                'frame_index': 1,
                'hands': [
                    {
                        'hand_type': 'Right',
                        'landmarks': {'0': {'x': 0.6, 'y': 0.6}},
                        'palm_center': {'x': 0.6, 'y': 0.6},
                        'finger_angles': {},
                        'hand_openness': 0.9
                    }
                ]
            }
        ]

        formatted = self.service._format_skeleton_data(raw_results)

        # 検証
        assert len(formatted) == 2, "2フレーム分のデータが生成されるべき"
        assert formatted[0]['frame'] == 0
        assert formatted[0]['frame_number'] == 0
        assert formatted[0]['timestamp'] == 0.0
        assert len(formatted[0]['hands']) == 1
        assert formatted[0]['hands'][0]['hand_type'] == 'Left'

        assert formatted[1]['frame'] == 6  # frame_skip=6 (30fps/5fps)
        assert formatted[1]['timestamp'] == 0.2  # 6/30 = 0.2
        assert len(formatted[1]['hands']) == 1
        assert formatted[1]['hands'][0]['hand_type'] == 'Right'

    def test_format_without_frame_index_fails(self):
        """異常系: frame_indexが欠損している場合はValueError"""
        raw_results = [
            {
                'detected': True,
                # 'frame_index': 0,  ← 意図的に欠如
                'hands': [
                    {
                        'hand_type': 'Left',
                        'landmarks': {},
                        'palm_center': {},
                        'finger_angles': {},
                        'hand_openness': 0.8
                    }
                ]
            }
        ]

        # ValueError が発生することを期待
        with pytest.raises(ValueError) as exc_info:
            self.service._format_skeleton_data(raw_results)

        # エラーメッセージの検証
        assert "frame_index" in str(exc_info.value)
        assert "skeleton_detector.detect_batch()" in str(exc_info.value)

    def test_format_empty_results(self):
        """エッジケース: 空のデータ"""
        raw_results = []
        formatted = self.service._format_skeleton_data(raw_results)
        assert len(formatted) == 0

    def test_format_no_detection(self):
        """エッジケース: 検出なし"""
        raw_results = [
            {
                'detected': False,
                'frame_index': 0,
                'hands': []
            }
        ]
        formatted = self.service._format_skeleton_data(raw_results)
        assert len(formatted) == 0

    def test_format_non_dict_result(self):
        """エッジケース: dict以外の要素はスキップ"""
        raw_results = [
            "invalid_string",
            {'detected': True, 'frame_index': 0, 'hands': [
                {'hand_type': 'Left', 'landmarks': {}, 'palm_center': {}, 'finger_angles': {}, 'hand_openness': 0.5}
            ]},
            None,
            {'detected': True, 'frame_index': 1, 'hands': [
                {'hand_type': 'Right', 'landmarks': {}, 'palm_center': {}, 'finger_angles': {}, 'hand_openness': 0.6}
            ]}
        ]

        formatted = self.service._format_skeleton_data(raw_results)

        # 有効な2つのdictのみ処理される
        assert len(formatted) == 2

    def test_format_multiple_hands_per_frame(self):
        """両手が検出された場合: 同じフレームに複数の手"""
        raw_results = [
            {
                'detected': True,
                'frame_index': 0,
                'hands': [
                    {'hand_type': 'Left', 'landmarks': {}, 'palm_center': {}, 'finger_angles': {}, 'hand_openness': 0.7},
                    {'hand_type': 'Right', 'landmarks': {}, 'palm_center': {}, 'finger_angles': {}, 'hand_openness': 0.8}
                ]
            }
        ]

        formatted = self.service._format_skeleton_data(raw_results)

        assert len(formatted) == 1  # 1フレーム
        assert len(formatted[0]['hands']) == 2  # 2つの手
        assert formatted[0]['hands'][0]['hand_type'] == 'Left'
        assert formatted[0]['hands'][1]['hand_type'] == 'Right'

    def test_format_preserves_hand_data_fields(self):
        """手のデータフィールドが正しく保持される"""
        raw_results = [
            {
                'detected': True,
                'frame_index': 0,
                'hands': [
                    {
                        'hand_type': 'Left',
                        'label': 'Left',  # labelフィールドもサポート
                        'landmarks': {'0': {'x': 0.1, 'y': 0.2}},
                        'palm_center': {'x': 0.5, 'y': 0.5},
                        'finger_angles': {'thumb': 45.0},
                        'hand_openness': 0.75
                    }
                ]
            }
        ]

        formatted = self.service._format_skeleton_data(raw_results)
        hand = formatted[0]['hands'][0]

        assert hand['hand_type'] == 'Left'
        assert hand['landmarks'] == {'0': {'x': 0.1, 'y': 0.2}}
        assert hand['palm_center'] == {'x': 0.5, 'y': 0.5}
        assert hand['finger_angles'] == {'thumb': 45.0}
        assert hand['hand_openness'] == 0.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
