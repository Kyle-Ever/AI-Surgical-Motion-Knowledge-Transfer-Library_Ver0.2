"""サンプル動画を生成するスクリプト"""
import cv2
import numpy as np
import os

def create_sample_video():
    # 出力パス
    output_path = "frontend/public/sample-video.mp4"
    
    # 動画の設定
    width = 640
    height = 360
    fps = 30
    duration = 5  # 5秒
    total_frames = fps * duration
    
    # 動画ライター設定
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        print("Error: VideoWriter could not be opened")
        return False
    
    # フレームを生成
    for i in range(total_frames):
        # グラデーション背景を作成
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 背景色のグラデーション
        color = int(128 + 127 * np.sin(2 * np.pi * i / total_frames))
        frame[:, :] = (color // 2, color // 3, color)
        
        # 移動する円を描画
        x = int(width * (0.2 + 0.6 * (i / total_frames)))
        y = int(height / 2 + 50 * np.sin(4 * np.pi * i / total_frames))
        cv2.circle(frame, (x, y), 30, (255, 255, 0), -1)
        
        # テキストを追加
        text = f"Sample Video Frame {i+1}/{total_frames}"
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # 手術器具をシミュレート（長方形）
        tool_x = int(width * 0.7 - 100 * np.sin(2 * np.pi * i / total_frames))
        tool_y = int(height * 0.6)
        cv2.rectangle(frame, (tool_x - 40, tool_y - 10), (tool_x + 40, tool_y + 10), (0, 255, 0), 2)
        
        # フレームを書き込み
        out.write(frame)
    
    # クリーンアップ
    out.release()
    
    if os.path.exists(output_path):
        print(f"Sample video created successfully at {output_path}")
        print(f"File size: {os.path.getsize(output_path) / 1024:.2f} KB")
        return True
    else:
        print("Error: Video file was not created")
        return False

if __name__ == "__main__":
    create_sample_video()