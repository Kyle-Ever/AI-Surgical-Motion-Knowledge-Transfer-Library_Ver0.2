"""
両手検出のテストスクリプト
DualVideoSection.tsxとScoringServiceの修正が正しく動作するか確認
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

# 既存の比較IDを使用
COMPARISON_ID = "c58cea02-4fdd-484b-81cc-017662d7dddf"

def test_comparison_with_skeleton_data():
    """比較データに両手のスケルトンデータが含まれているか確認"""

    print(f"比較ID {COMPARISON_ID} のデータを取得中...")

    # 比較データを取得
    response = requests.get(f"{BASE_URL}/scoring/comparison/{COMPARISON_ID}")

    if response.status_code != 200:
        print(f"エラー: ステータスコード {response.status_code}")
        print(response.text)
        return

    data = response.json()

    # 学習者の分析IDを取得
    learner_analysis_id = data.get('learner_analysis_id')
    if learner_analysis_id:
        print(f"\n学習者の分析ID: {learner_analysis_id}")

        # 学習者の分析データを取得
        analysis_response = requests.get(f"{BASE_URL}/analysis/{learner_analysis_id}")
        if analysis_response.status_code == 200:
            analysis_data = analysis_response.json()
            skeleton_data = analysis_data.get('skeleton_data', [])

            if skeleton_data:
                print(f"  - スケルトンフレーム数: {len(skeleton_data)}")

                # 両手が検出されているフレームを探す
                both_hands_frames = []
                left_hand_frames = []
                right_hand_frames = []

                # タイムスタンプごとにグループ化
                timestamp_groups = {}
                for frame in skeleton_data:
                    timestamp = frame.get('timestamp', 0)
                    if timestamp not in timestamp_groups:
                        timestamp_groups[timestamp] = []
                    timestamp_groups[timestamp].append(frame)

                # 各タイムスタンプで両手が検出されているか確認
                for timestamp, frames in timestamp_groups.items():
                    hands_in_timestamp = set()
                    for frame in frames:
                        hand_type = frame.get('hand_type', 'Unknown')
                        hands_in_timestamp.add(hand_type)

                        if hand_type == 'Left':
                            left_hand_frames.append(frame)
                        elif hand_type == 'Right':
                            right_hand_frames.append(frame)

                    if 'Left' in hands_in_timestamp and 'Right' in hands_in_timestamp:
                        both_hands_frames.append(timestamp)

                print(f"  - 左手検出フレーム数: {len(left_hand_frames)}")
                print(f"  - 右手検出フレーム数: {len(right_hand_frames)}")
                print(f"  - 両手同時検出タイムスタンプ数: {len(both_hands_frames)}")

                if both_hands_frames:
                    print(f"  ✅ 両手が同時に検出されています！")
                    print(f"     最初の両手検出: {both_hands_frames[0]:.2f}秒")
                    print(f"     最後の両手検出: {both_hands_frames[-1]:.2f}秒")
                else:
                    print(f"  ⚠️ 両手の同時検出が見つかりません")

                # サンプルフレームの詳細を表示
                if timestamp_groups:
                    sample_timestamp = list(timestamp_groups.keys())[0]
                    sample_frames = timestamp_groups[sample_timestamp]
                    print(f"\n  サンプル（タイムスタンプ {sample_timestamp:.2f}秒）:")
                    for frame in sample_frames:
                        print(f"    - {frame.get('hand_type', 'Unknown')}手")
                        if 'landmarks' in frame and frame['landmarks']:
                            print(f"      ランドマーク数: {len(frame['landmarks'])}")
            else:
                print(f"  ⚠️ スケルトンデータが空です")

    # DTW計算結果を確認
    if 'feedback' in data and data['feedback']:
        feedback = data['feedback']
        if 'detailed_analysis' in feedback and feedback['detailed_analysis']:
            detailed = feedback['detailed_analysis']
            if 'trajectory_analysis' in detailed:
                print(f"\n軌跡分析:")
                traj = detailed['trajectory_analysis']
                print(f"  - DTW距離: {traj.get('dtw_distance', 'N/A')}")

if __name__ == "__main__":
    test_comparison_with_skeleton_data()
