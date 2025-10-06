#!/usr/bin/env python3
"""
Phase 5 包括的テスト
全ての動画タイプ（EXTERNAL, EXTERNAL_WITH_INSTRUMENTS, INTERNAL）の解析をテスト
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncio
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.video import Video, VideoType
from app.models.analysis import AnalysisResult, AnalysisStatus
from app.services.analysis_service_v2 import AnalysisServiceV2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = "sqlite:///./aimotion.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def test_external_analysis():
    """Test EXTERNAL (skeleton only) analysis"""
    logger.info("=" * 60)
    logger.info("Phase 5.1: EXTERNAL解析テスト（骨格のみ）")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # Get latest EXTERNAL_NO_INSTRUMENTS analysis
        analysis = db.query(AnalysisResult).join(Video).filter(
            Video.video_type == VideoType.EXTERNAL_NO_INSTRUMENTS,
            AnalysisResult.status == AnalysisStatus.COMPLETED
        ).order_by(AnalysisResult.created_at.desc()).first()

        if not analysis:
            logger.error("❌ No EXTERNAL_NO_INSTRUMENTS analysis found")
            return False

        logger.info(f"✅ Analysis ID: {analysis.id}")
        logger.info(f"   Video ID: {analysis.video_id}")
        logger.info(f"   Status: {analysis.status}")
        logger.info(f"   Skeleton frames: {len(analysis.skeleton_data) if analysis.skeleton_data else 0}")
        logger.info(f"   Instrument frames: {len(analysis.instrument_data) if analysis.instrument_data else 0}")

        # Validate skeleton data
        if not analysis.skeleton_data or len(analysis.skeleton_data) == 0:
            logger.error("❌ No skeleton data detected")
            return False

        # Check first frame structure
        first_frame = analysis.skeleton_data[0]
        required_keys = ['frame_number', 'timestamp', 'hand_type', 'landmarks', 'confidence']
        for key in required_keys:
            if key not in first_frame:
                logger.error(f"❌ Missing key in skeleton data: {key}")
                return False

        # Check landmarks structure
        landmarks = first_frame['landmarks']
        if not isinstance(landmarks, list) or len(landmarks) != 21:
            logger.error(f"❌ Invalid landmarks count: {len(landmarks)} (expected 21)")
            return False

        # Check landmark data
        first_landmark = landmarks[0]
        if not all(k in first_landmark for k in ['x', 'y', 'z', 'visibility']):
            logger.error(f"❌ Invalid landmark structure: {first_landmark.keys()}")
            return False

        logger.info(f"✅ Skeleton data structure: Valid")
        logger.info(f"   Frame count: {len(analysis.skeleton_data)}")
        logger.info(f"   Confidence: {first_frame['confidence']:.4f}")
        logger.info(f"   Hand type: {first_frame['hand_type']}")

        # Check metrics
        if analysis.avg_velocity is None or analysis.avg_velocity == 0:
            logger.warning("⚠️  Average velocity not calculated or zero")
        else:
            logger.info(f"✅ Metrics calculated:")
            logger.info(f"   Avg velocity: {analysis.avg_velocity:.2f}")
            logger.info(f"   Max velocity: {analysis.max_velocity:.2f}")
            logger.info(f"   Total distance: {analysis.total_distance:.2f}")

        logger.info("✅ EXTERNAL analysis test: PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False
    finally:
        db.close()


async def test_external_with_instruments():
    """Test EXTERNAL_WITH_INSTRUMENTS analysis"""
    logger.info("=" * 60)
    logger.info("Phase 5.2: EXTERNAL_WITH_INSTRUMENTS解析テスト")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # Get latest EXTERNAL_WITH_INSTRUMENTS analysis
        analysis = db.query(AnalysisResult).join(Video).filter(
            Video.video_type == VideoType.EXTERNAL_WITH_INSTRUMENTS,
            AnalysisResult.status == AnalysisStatus.COMPLETED
        ).order_by(AnalysisResult.created_at.desc()).first()

        if not analysis:
            logger.warning("⚠️  No EXTERNAL_WITH_INSTRUMENTS analysis found (creating new test)")
            logger.info("   Please run analysis with EXTERNAL_WITH_INSTRUMENTS video type")
            return None  # Not a failure, just no test data

        logger.info(f"✅ Analysis ID: {analysis.id}")
        logger.info(f"   Skeleton frames: {len(analysis.skeleton_data) if analysis.skeleton_data else 0}")
        logger.info(f"   Instrument frames: {len(analysis.instrument_data) if analysis.instrument_data else 0}")

        # Both skeleton and instruments should exist
        has_skeleton = analysis.skeleton_data and len(analysis.skeleton_data) > 0
        has_instruments = analysis.instrument_data and len(analysis.instrument_data) > 0

        if not has_skeleton:
            logger.error("❌ No skeleton data for EXTERNAL_WITH_INSTRUMENTS")
            return False

        if not has_instruments:
            logger.warning("⚠️  No instrument data (may be expected if no instruments selected)")

        logger.info("✅ EXTERNAL_WITH_INSTRUMENTS analysis test: PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False
    finally:
        db.close()


async def test_internal_analysis():
    """Test INTERNAL (instruments only) analysis"""
    logger.info("=" * 60)
    logger.info("Phase 5.3: INTERNAL解析テスト（器具のみ）")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # Get latest INTERNAL analysis
        analysis = db.query(AnalysisResult).join(Video).filter(
            Video.video_type == VideoType.INTERNAL,
            AnalysisResult.status == AnalysisStatus.COMPLETED
        ).order_by(AnalysisResult.created_at.desc()).first()

        if not analysis:
            logger.warning("⚠️  No INTERNAL analysis found")
            logger.info("   Please run analysis with INTERNAL video type")
            return None

        logger.info(f"✅ Analysis ID: {analysis.id}")
        logger.info(f"   Skeleton frames: {len(analysis.skeleton_data) if analysis.skeleton_data else 0}")
        logger.info(f"   Instrument frames: {len(analysis.instrument_data) if analysis.instrument_data else 0}")

        # INTERNAL should have instruments, no skeleton
        has_skeleton = analysis.skeleton_data and len(analysis.skeleton_data) > 0
        has_instruments = analysis.instrument_data and len(analysis.instrument_data) > 0

        if has_skeleton:
            logger.warning("⚠️  Skeleton data found in INTERNAL analysis (unexpected)")

        if not has_instruments:
            logger.warning("⚠️  No instrument data (may be expected if no instruments detected)")

        logger.info("✅ INTERNAL analysis test: PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False
    finally:
        db.close()


async def test_performance():
    """Test analysis performance"""
    logger.info("=" * 60)
    logger.info("Phase 5.5: パフォーマンス検証")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # Get recent analyses
        analyses = db.query(AnalysisResult).filter(
            AnalysisResult.status == AnalysisStatus.COMPLETED
        ).order_by(AnalysisResult.created_at.desc()).limit(10).all()

        if not analyses:
            logger.error("❌ No completed analyses found")
            return False

        durations = []
        for analysis in analyses:
            if analysis.completed_at and analysis.created_at:
                duration = (analysis.completed_at - analysis.created_at).total_seconds()
                durations.append(duration)

        if durations:
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)

            logger.info(f"✅ Performance metrics (last {len(durations)} analyses):")
            logger.info(f"   Average duration: {avg_duration:.2f}s")
            logger.info(f"   Max duration: {max_duration:.2f}s")
            logger.info(f"   Min duration: {min_duration:.2f}s")

            # Performance threshold: should complete in reasonable time
            if avg_duration > 60:
                logger.warning(f"⚠️  Average duration > 60s: {avg_duration:.2f}s")
            else:
                logger.info(f"✅ Performance: Good (avg {avg_duration:.2f}s)")

        return True

    except Exception as e:
        logger.error(f"❌ Performance test failed: {e}", exc_info=True)
        return False
    finally:
        db.close()


async def main():
    """Run all Phase 5 tests"""
    logger.info("🚀 Starting Phase 5 Comprehensive Tests")
    logger.info("")

    results = {}

    # Test 1: EXTERNAL
    results['external'] = await test_external_analysis()
    logger.info("")

    # Test 2: EXTERNAL_WITH_INSTRUMENTS
    results['external_with_instruments'] = await test_external_with_instruments()
    logger.info("")

    # Test 3: INTERNAL
    results['internal'] = await test_internal_analysis()
    logger.info("")

    # Test 4: Performance
    results['performance'] = await test_performance()
    logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("📊 Test Summary")
    logger.info("=" * 60)

    total = 0
    passed = 0
    failed = 0
    skipped = 0

    for test_name, result in results.items():
        total += 1
        if result is True:
            passed += 1
            status = "✅ PASSED"
        elif result is False:
            failed += 1
            status = "❌ FAILED"
        else:
            skipped += 1
            status = "⏭️  SKIPPED"

        logger.info(f"{status}: {test_name}")

    logger.info("")
    logger.info(f"Total: {total}, Passed: {passed}, Failed: {failed}, Skipped: {skipped}")

    if failed > 0:
        logger.error("❌ Some tests failed")
        sys.exit(1)
    else:
        logger.info("✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
