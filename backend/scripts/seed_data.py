#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 시드 데이터 생성 스크립트
목업 데이터를 데이터베이스에 추가합니다.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app import app, db
from models import EMSTeam, Hospital
from utils.password import hash_password


def seed_ems_teams():
    """구급차 팀 목업 데이터 생성"""
    teams = [
        {
            "ems_id": "ems_001",
            "password": "password123",  # 평문 비밀번호 (해시로 변환됨)
            "region": "서울특별시"
        },
        {
            "ems_id": "ems_002",
            "password": "password123",
            "region": "경기도"
        },
        {
            "ems_id": "ems_003",
            "password": "password123",
            "region": "광주광역시"
        },
    ]
    
    for team_data in teams:
        # 이미 존재하는지 확인
        existing = EMSTeam.query.filter_by(ems_id=team_data["ems_id"]).first()
        if existing:
            print(f"⚠️  {team_data['ems_id']}는 이미 존재합니다. 건너뜁니다.")
            continue
        
        # 비밀번호 해시
        hashed_password = hash_password(team_data["password"])
        
        # 팀 생성
        team = EMSTeam(
            ems_id=team_data["ems_id"],
            password=hashed_password,  # 해시된 비밀번호 저장
            region=team_data["region"]
        )
        
        db.session.add(team)
        print(f"✅ {team_data['ems_id']} 팀 생성 완료 (지역: {team_data['region']})")
    
    db.session.commit()
    print(f"\n✅ 총 {len(teams)}개의 구급차 팀 데이터가 생성되었습니다.")


def migrate_hospital_password_column():
    """Hospital 테이블에 password 컬럼 추가 (마이그레이션)"""
    from sqlalchemy import inspect, text
    
    try:
        # SQLAlchemy Inspector 사용
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('hospital')]
        
        if 'password' not in columns:
            print("📝 Hospital 테이블에 password 컬럼 추가 중...")
            db.session.execute(text("ALTER TABLE hospital ADD COLUMN password VARCHAR(255)"))
            db.session.commit()
            print("✅ password 컬럼 추가 완료")
            return True
        else:
            print("✅ password 컬럼이 이미 존재합니다.")
            return True
    except Exception as e:
        # Inspector가 실패하면 PRAGMA 사용
        try:
            db.session.rollback()
            result = db.session.execute(text("PRAGMA table_info(hospital)"))
            columns = [row[1] for row in result]
            
            if 'password' not in columns:
                print("📝 Hospital 테이블에 password 컬럼 추가 중... (PRAGMA 방식)")
                db.session.execute(text("ALTER TABLE hospital ADD COLUMN password VARCHAR(255)"))
                db.session.commit()
                print("✅ password 컬럼 추가 완료")
                return True
            else:
                print("✅ password 컬럼이 이미 존재합니다.")
                return True
        except Exception as e2:
            print(f"⚠️  password 컬럼 추가 실패: {e2}")
            print("   수동으로 실행하세요: python scripts/migrate_db.py")
            return False


def seed_hospital_passwords():
    """병원 비밀번호 설정 (기존 병원에 기본 비밀번호 설정)"""
    # 먼저 컬럼이 있는지 확인하고 없으면 추가
    migrate_hospital_password_column()
    
    # 기본 비밀번호 (실제 운영 시에는 더 강력한 비밀번호 사용)
    default_password = "hospital123"
    hashed_password = hash_password(default_password)
    
    # 모든 병원 조회 (password 컬럼이 없을 수도 있으므로 try-except 사용)
    try:
        # 모든 병원에 비밀번호 설정 (password가 없는 경우만)
        hospitals = Hospital.query.filter(
            (Hospital.password == None) | (Hospital.password == "")
        ).all()
    except Exception as e:
        # password 컬럼이 없으면 모든 병원 조회
        print(f"⚠️  password 컬럼 조회 실패, 모든 병원에 비밀번호 설정 시도: {e}")
        hospitals = Hospital.query.all()
    
    if not hospitals:
        print("⚠️  병원이 없습니다.")
        return
    
    count = 0
    for hospital in hospitals:
        # password가 None이거나 빈 문자열인 경우만 설정
        try:
            if not hospital.password:
                hospital.password = hashed_password
                count += 1
                print(f"✅ {hospital.name} ({hospital.hospital_id}) 비밀번호 설정 완료")
        except AttributeError:
            # password 속성이 없으면 설정
            hospital.password = hashed_password
            count += 1
            print(f"✅ {hospital.name} ({hospital.hospital_id}) 비밀번호 설정 완료")
    
    if count > 0:
        db.session.commit()
        print(f"\n✅ 총 {count}개의 병원에 비밀번호가 설정되었습니다.")
        print(f"   기본 비밀번호: {default_password}")
        print(f"   ⚠️  실제 운영 시에는 각 병원별로 고유한 비밀번호를 설정하세요.")
    else:
        print("⚠️  비밀번호가 설정되지 않은 병원이 없습니다.")


# 병원 데이터는 국립중앙의료원 API에서 실시간으로 가져오므로
# 시드 데이터로 하드코딩하지 않습니다.
# 병원 정보는 app.py의 fetch_baseinfo_by_hpid() 함수를 통해
# API에서 동적으로 조회됩니다.


def main():
    """메인 함수"""
    print("=" * 60)
    print("🌱 데이터베이스 시드 데이터 생성 시작")
    print("=" * 60)
    
    with app.app_context():
        # 테이블 생성 (없으면)
        db.create_all()
        print("\n✅ 데이터베이스 테이블 확인 완료\n")
        
        # 시드 데이터 생성
        print("📦 구급차 팀 데이터 생성 중...")
        seed_ems_teams()
        
        print("\n📦 병원 비밀번호 설정 중...")
        seed_hospital_passwords()
        
        print("\n💡 병원 데이터는 국립중앙의료원 API에서 실시간으로 조회됩니다.")
        print("   시드 데이터로 하드코딩하지 않습니다.")
        
        print("\n" + "=" * 60)
        print("✅ 시드 데이터 생성 완료!")
        print("=" * 60)
        print("\n💡 참고:")
        print("   - 구급차 팀 기본 비밀번호: password123")
        print("   - 비밀번호는 해시되어 저장되었습니다.")
        print("   - 실제 운영 시에는 더 강력한 비밀번호를 사용하세요.")
        print("   - 병원 데이터는 국립중앙의료원 API에서 실시간 조회됩니다.")


if __name__ == "__main__":
    main()

