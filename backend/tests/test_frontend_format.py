#!/usr/bin/env python3
"""
フロントエンド形式テスト
skeleton_dataがフロントエンド期待形式になっているか確認
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.analysis import AnalysisResult, AnalysisStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = "sqlite:///./aimotion.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_skeleton_format():
    """Test skeleton data format"""
    logger.info("=" * 60)
    logger.info("フロントエンド形式テスト")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # Get latest completed analysis
        analysis = db.query(AnalysisResult).filter(
            AnalysisResult.status == AnalysisStatus.COMPLETED
        ).order_by(AnalysisResult.created_at.desc()).first()

        if not analysis:
            logger.error("❌ No completed analysis found")
            return False

        if not analysis.skeleton_data or len(analysis.skeleton_data) == 0:
            logger.warning("⚠️  No skeleton data")
            return None

        logger.info(f"✅ Analysis ID: {analysis.id}")
        logger.info(f"   Skeleton frames: {len(analysis.skeleton_data)}")

        # Check first frame structure
        first_frame = analysis.skeleton_data[0]
        logger.info(f"\n📋 First frame structure:")
        logger.info(f"   Keys: {list(first_frame.keys())}")

        # Expected keys for frontend
        expected_keys = ['frame', 'frame_number', 'timestamp', 'hands']

        for key in expected_keys:
            if key not in first_frame:
                logger.error(f"❌ Missing expected key: {key}")
                return False
            logger.info(f"   ✅ {key}: {type(first_frame[key]).__name__}")

        # Check 'hands' structure
        if not isinstance(first_frame.get('hands'), list):
            logger.error(f"❌ 'hands' should be list, got: {type(first_frame.get('hands'))}")
            return False

        hands_count = len(first_frame.get('hands', []))
        logger.info(f"   Hands in first frame: {hands_count}")

        if hands_count > 0:
            first_hand = first_frame['hands'][0]
            logger.info(f"\n🖐️  First hand structure:")
            logger.info(f"   Keys: {list(first_hand.keys())}")

            expected_hand_keys = ['hand_type', 'landmarks']
            for key in expected_hand_keys:
                if key in first_hand:
                    logger.info(f"   ✅ {key}: {type(first_hand[key]).__name__}")
                else:
                    logger.warning(f"   ⚠️  Missing: {key}")

        logger.info(f"\n✅ Format check: PASSED")
        logger.info(f"   Total frames: {len(analysis.skeleton_data)}")
        logger.info(f"   Format: Frontend compatible (1 frame = multiple hands)")

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False
    finally:
        db.close()


if __name__ == "__main__":
    result = test_skeleton_format()
    sys.exit(0 if result else 1)
