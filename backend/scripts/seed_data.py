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
from models import EMSTeam
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
            "region": "부산광역시"
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

