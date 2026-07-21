#!/usr/bin/env python
"""Verify that all Phase 3 components are properly set up."""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("PHASE 3 VERIFICATION")
print("=" * 70)

# Test 1: Config Loading
print("\n[1] Testing Configuration...")
try:
    from app.core.config import settings
    print(f"    [OK] Settings loaded successfully")
    print(f"    [OK] DATABASE_URL: {settings.DATABASE_URL[:40]}...")
    print(f"    [OK] PROJECT_NAME: {settings.PROJECT_NAME}")
except Exception as e:
    print(f"    [FAIL] Failed to load settings: {e}")
    sys.exit(1)

# Test 2: Database Module
print("\n[2] Testing Database Module...")
try:
    from app.db.database import get_engine, get_async_session_maker
    print(f"    [OK] Database module functions imported (lazy-loaded)")
    print(f"    [NOTE] Engine connection will be created on first use")
except Exception as e:
    print(f"    [FAIL] Failed to import database functions: {e}")
    sys.exit(1)

# Test 3: Models
print("\n[3] Testing Database Models...")
try:
    from app.db.models import Base, User, Post, PostStatus
    print(f"    [OK] Base imported successfully")
    print(f"    [OK] User model imported")
    print(f"    [OK] Post model imported")
    print(f"    [OK] PostStatus enum imported")

    # Check tables
    print(f"\n    Tables in Base.metadata:")
    for table_name in Base.metadata.tables.keys():
        print(f"      - {table_name}")
        table = Base.metadata.tables[table_name]
        for col in table.columns:
            print(f"        • {col.name}: {col.type}")
except Exception as e:
    print(f"    [FAIL] Failed to import models: {e}")
    sys.exit(1)

# Test 4: LangGraph State
print("\n[4] Testing LangGraph State...")
try:
    from app.agent.state import AgentState
    print(f"    [OK] AgentState imported successfully")

    # Check state fields
    print(f"\n    AgentState fields:")
    for field_name, field_type in AgentState.__annotations__.items():
        print(f"      - {field_name}: {field_type}")
except Exception as e:
    print(f"    [FAIL] Failed to import AgentState: {e}")
    sys.exit(1)

# Test 5: Alembic Migration File
print("\n[5] Testing Alembic Migration...")
try:
    migration_file = Path(__file__).parent / "alembic" / "versions" / "001_initial_migration.py"
    if migration_file.exists():
        print(f"    [OK] Migration file exists: {migration_file.name}")
        with open(migration_file) as f:
            content = f.read()
            if "def upgrade()" in content and "def downgrade()" in content:
                print(f"    [OK] Migration contains upgrade and downgrade functions")
            if "CREATE TABLE users" in content or "CREATE TABLE posts" in content or "'users'" in content:
                print(f"    [OK] Migration contains table definitions")
    else:
        print(f"    [FAIL] Migration file not found")
        sys.exit(1)
except Exception as e:
    print(f"    [FAIL] Failed to verify migration: {e}")
    sys.exit(1)

# Test 6: Database Package Initialization
print("\n[6] Testing Database Package...")
try:
    from app.db import (
        Base, User, Post, PostStatus,
        get_engine, get_async_session_maker, get_db_session
    )
    print(f"    [OK] All exports from app.db are accessible")
    print(f"    [OK] Lazy-loading functions ready for use")
except Exception as e:
    print(f"    [FAIL] Failed to import from app.db: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("[SUCCESS] ALL PHASE 3 COMPONENTS VERIFIED SUCCESSFULLY!")
print("=" * 70)
print("\nNext Steps:")
print("  1. Set up PostgreSQL database if not already running")
print("  2. Run: alembic upgrade head")
print("  3. Proceed to Phase 4: Agent Logic Implementation")
