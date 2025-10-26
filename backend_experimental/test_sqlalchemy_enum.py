#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLAlchemy Enumの動作を検証 - なぜ大文字になるのか
"""
import sys
import enum
from sqlalchemy import create_engine, Column, String, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

Base = declarative_base()

class TestStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TestModel(Base):
    __tablename__ = "test_model"
    id = Column(String, primary_key=True)
    status = Column(Enum(TestStatus), nullable=False)

def test_enum_behavior():
    print("=" * 80)
    print("SQLAlchemy Enum Behavior Test - Why Uppercase?")
    print("=" * 80)

    # Create in-memory SQLite database
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("\n[1] Python Enum Definition")
    print("-" * 80)
    print("class TestStatus(str, enum.Enum):")
    print("    PENDING = 'pending'")
    print("    PROCESSING = 'processing'")
    print("    COMPLETED = 'completed'")
    print("    FAILED = 'failed'")

    print("\n[2] Inserting Data with Enum Values")
    print("-" * 80)

    # Insert using Enum
    test1 = TestModel(id="1", status=TestStatus.COMPLETED)
    session.add(test1)
    session.commit()

    print(f"   Inserted: TestModel(id='1', status=TestStatus.COMPLETED)")
    print(f"   Enum value: '{TestStatus.COMPLETED.value}'")
    print(f"   Enum name: '{TestStatus.COMPLETED.name}'")

    # Query back
    result = session.query(TestModel).filter(TestModel.id == "1").first()
    print(f"\n   Queried back:")
    print(f"   result.status = {result.status}")
    print(f"   result.status.value = '{result.status.value}'")
    print(f"   result.status.name = '{result.status.name}'")

    # Check raw SQL
    print("\n[3] Raw SQL Check")
    print("-" * 80)
    from sqlalchemy import text
    raw_result = session.execute(text("SELECT status FROM test_model WHERE id = '1'")).fetchone()
    print(f"   Raw SQL result: '{raw_result[0]}'")

    # Test comparison
    print("\n[4] Comparison Tests")
    print("-" * 80)

    # Enum comparison
    result_enum = session.query(TestModel).filter(
        TestModel.status == TestStatus.COMPLETED
    ).first()
    print(f"   Query with Enum: TestModel.status == TestStatus.COMPLETED")
    print(f"   Result: {'FOUND' if result_enum else 'NOT FOUND'}")

    # String comparison (lowercase)
    result_lower = session.query(TestModel).filter(
        TestModel.status == 'completed'
    ).first()
    print(f"\n   Query with lowercase string: TestModel.status == 'completed'")
    print(f"   Result: {'FOUND' if result_lower else 'NOT FOUND'}")

    # String comparison (uppercase)
    result_upper = session.query(TestModel).filter(
        TestModel.status == 'COMPLETED'
    ).first()
    print(f"\n   Query with uppercase string: TestModel.status == 'COMPLETED'")
    print(f"   Result: {'FOUND' if result_upper else 'NOT FOUND'}")

    # Case-insensitive comparison
    from sqlalchemy import func
    result_ci = session.query(TestModel).filter(
        func.lower(TestModel.status) == 'completed'
    ).first()
    print(f"\n   Query with func.lower: func.lower(TestModel.status) == 'completed'")
    print(f"   Result: {'FOUND' if result_ci else 'NOT FOUND'}")

    session.close()

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("""
    SQLAlchemy stores Enum values based on:
    1. The Enum's VALUE (not the NAME)
    2. SQLite stores text exactly as provided
    3. When querying with Enum, SQLAlchemy compares by value

    In this test:
    - Enum definition: COMPLETED = "completed" (lowercase value)
    - Stored in DB: "completed" (lowercase)
    - Query with Enum: Works (compares value)
    - Query with lowercase string: Works
    - Query with uppercase string: Does NOT work

    BUT in the actual database:
    - Stored value is "COMPLETED" (uppercase)

    This means:
    1. Either the Enum definition was UPPERCASE in the past
    2. Or there's explicit uppercase conversion somewhere
    3. Or Alembic migration used uppercase values

    Need to check:
    - Git history of Enum definition
    - Alembic migration files
    - Any explicit .upper() calls during insertion
    """)

if __name__ == "__main__":
    test_enum_behavior()
