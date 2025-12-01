#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 마이그레이션 스크립트
기존 DB에 새로운 컬럼을 추가하거나 스키마를 업데이트합니다.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app import app, db
from sqlalchemy import text, inspect
from models import APICallLog


def check_column_exists(table_name: str, column_name: str) -> bool:
    """테이블에 컬럼이 존재하는지 확인"""
    try:
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        # inspector가 작동하지 않으면 PRAGMA 사용
        try:
            result = db.session.execute(text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result]
            return column_name in columns
        except Exception as e2:
            print(f"⚠️  컬럼 확인 실패: {e2}")
            return False


def add_hospital_password_column():
    """Hospital 테이블에 password 컬럼 추가"""
    table_name = "hospital"
    column_name = "password"
    
    if check_column_exists(table_name, column_name):
        print(f"✅ {table_name}.{column_name} 컬럼이 이미 존재합니다.")
        return True
    
    try:
        print(f"📝 {table_name} 테이블에 {column_name} 컬럼 추가 중...")
        db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} VARCHAR(255)"))
        db.session.commit()
        print(f"✅ {column_name} 컬럼 추가 완료")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ {column_name} 컬럼 추가 실패: {e}")
        print(f"   수동으로 실행: ALTER TABLE {table_name} ADD COLUMN {column_name} VARCHAR(255)")
        return False


def add_chat_session_is_deleted_column():
    """ChatSession 테이블에 is_deleted 컬럼 추가"""
    table_name = "chat_session"
    column_name = "is_deleted"
    
    if check_column_exists(table_name, column_name):
        print(f"✅ {table_name}.{column_name} 컬럼이 이미 존재합니다.")
        return True
    
    try:
        print(f"📝 {table_name} 테이블에 {column_name} 컬럼 추가 중...")
        db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} BOOLEAN DEFAULT 0"))
        db.session.commit()
        print(f"✅ {column_name} 컬럼 추가 완료")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ {column_name} 컬럼 추가 실패: {e}")
        print(f"   수동으로 실행: ALTER TABLE {table_name} ADD COLUMN {column_name} BOOLEAN DEFAULT 0")
        return False


def create_api_call_log_table():
    """APICallLog 테이블 생성"""
    table_name = "api_call_log"
    
    try:
        # 테이블이 이미 존재하는지 확인
        inspector = inspect(db.engine)
        if table_name in inspector.get_table_names():
            print(f"✅ {table_name} 테이블이 이미 존재합니다.")
            return True
        
        # 테이블 생성
        print(f"📝 {table_name} 테이블 생성 중...")
        db.create_all()  # 모든 모델의 테이블 생성
        print(f"✅ {table_name} 테이블 생성 완료")
        return True
    except Exception as e:
        print(f"❌ {table_name} 테이블 생성 실패: {e}")
        return False


def migrate_all():
    """모든 마이그레이션 실행"""
    print("=" * 60)
    print("🔄 데이터베이스 마이그레이션 시작")
    print("=" * 60)
    
    with app.app_context():
        migrations = [
            ("Hospital.password 컬럼 추가", add_hospital_password_column),
            ("ChatSession.is_deleted 컬럼 추가", add_chat_session_is_deleted_column),
            ("APICallLog 테이블 생성", create_api_call_log_table),
        ]
        
        success_count = 0
        for name, migration_func in migrations:
            print(f"\n📦 {name}...")
            if migration_func():
                success_count += 1
            else:
                print(f"⚠️  {name} 실패")
        
        print("\n" + "=" * 60)
        if success_count == len(migrations):
            print("✅ 모든 마이그레이션이 완료되었습니다!")
        else:
            print(f"⚠️  {success_count}/{len(migrations)} 마이그레이션 완료")
        print("=" * 60)


if __name__ == "__main__":
    migrate_all()

