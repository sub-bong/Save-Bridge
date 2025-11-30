from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy 객체 생성 (Flask 앱은 app.py에서 초기화)
# app.py에서 db.init_app(app)로 연결됨
db = SQLAlchemy()


#### 구급차 정보
class EMSTeam(db.Model):
    __tablename__ = 'ems_team'
    
    # 컬럼 정의
    team_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ems_id = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False) # 해시 .. 재확인 필요
    region = db.Column(db.String(100), nullable=True) # MVP 범위 설정용

    # 관계 정의 (이 팀이 요청한 모든 EmergencyRequest)
    requests = db.relationship('EmergencyRequest', backref='requester', lazy='dynamic')

    def __repr__(self):
        return f"EMSTeam('{self.ems_id}', '{self.region}')"



#### 응급실(병원) 정보
class Hospital(db.Model):
    __tablename__ = 'hospital'
    
    # 컬럼 정의
    hospital_id = db.Column(db.String(50), primary_key=True) # 기관 ID (PK)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    hospital_grade = db.Column(db.Text, nullable=True) #권역 응급, 지역응급, 외상센터
    phone_number = db.Column(db.String(50), nullable=True) #응급실 대표
    password = db.Column(db.String(255), nullable=True) # 로그인 비밀번호 (해시 저장)
    
    # 관계 정의 (이 병원이 받은 모든 RequestAssignment)
    assignments = db.relationship('RequestAssignment', backref='hospital_info', lazy='dynamic')

    def __repr__(self):
        return f"Hospital('{self.name}')"


#### 응급실 입실 요청 
class EmergencyRequest(db.Model):
    __tablename__ = 'emergency_request'
    
    # 컬럼 정의
    request_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey('ems_team.team_id'), nullable=False) # FK
    
    # 환자 기본 정보 (스프레드시트 User 테이블 정보 일부 반영)
    patient_sex = db.Column(db.String(20), nullable=False)
    patient_age = db.Column(db.Integer, nullable=False)

    # 요청 정보
    pre_ktas_class = db.Column(db.String(50), nullable=False)
    stt_full_text = db.Column(db.Text, nullable=True)
    rag_summary = db.Column(db.Text, nullable=True) # SBAR 변환 및 주요 증상 추출 결과
    current_lat = db.Column(db.Float, nullable=False) # 구급차 현 위치
    current_lon = db.Column(db.Float, nullable=False)
    is_completed = db.Column(db.Boolean, nullable=False, default=False) # 병원 인계완료 여부 
    requested_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    # 관계 정의 (이 요청과 관련된 모든 RequestAssignment, ChatSession)
    assignments = db.relationship('RequestAssignment', backref='request', lazy='dynamic')
    session = db.relationship('ChatSession', backref='request', uselist=False) # 1:1 관계

    def __repr__(self):
        return f"EmergencyRequest('{self.request_id}', '{self.pre_ktas_class}')"


#### 요청-병원 매칭 및 응답 기록
class RequestAssignment(db.Model):
    __tablename__ = 'request_assignment'
    
    # 컬럼 정의
    assignment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    request_id = db.Column(db.Integer, db.ForeignKey('emergency_request.request_id'), nullable=False) # FK
    hospital_id = db.Column(db.String(50), db.ForeignKey('hospital.hospital_id'), nullable=False) # FK
    
    twillio_sid = db.Column(db.String(255), nullable=True) # ARS 호출 번호 (Twilio Call SID)
    response_status = db.Column(db.String(20), nullable=False, default='대기중') # '대기중', '승인', '거절'
    distance_km = db.Column(db.Float, nullable=True) # 거리 (km)
    eta_min = db.Column(db.Integer, nullable=True) # 예상 소요 시간 (분)
    responded_at = db.Column(db.DateTime, nullable=True) # 응답 시간
    called_at = db.Column(db.DateTime, nullable=True) # 전화 건 시간

    # 관계 정의 (이 매칭이 수락되었을 경우의 ChatSession)
    session = db.relationship('ChatSession', backref='assignment', uselist=False) # 1:1 관계

    def __repr__(self):
        return f"Assignment('{self.assignment_id}', Status='{self.response_status}')"


#### 채팅 세션 정보 
class ChatSession(db.Model):
    __tablename__ = 'chat_session'
    
    # 컬럼 정의
    session_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # RequestAssignment 테이블에서 ACCEPT된 경우에만 연결되므로 Unique 제약조건 추가
    request_id = db.Column(db.Integer, db.ForeignKey('emergency_request.request_id'), unique=True, nullable=False) 
    assignment_id = db.Column(db.Integer, db.ForeignKey('request_assignment.assignment_id'), unique=True, nullable=False)
    
    started_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp()) # 채팅 시작 시간
    ended_at = db.Column(db.DateTime, nullable=True, default=db.func.current_timestamp()) # 채팅 종료 시간 
    is_deleted = db.Column(db.Boolean, nullable=False, default=False) # 소프트 삭제 플래그

    # 관계 정의 (이 세션에 포함된 모든 ChatMessage)
    messages = db.relationship('ChatMessage', backref='session', lazy='dynamic')

    def __repr__(self):
        return f"ChatSession('{self.session_id}', Request='{self.request_id}')"


#### 채팅 메시지 내용 
class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    
    # 컬럼 정의
    message_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.session_id'), nullable=False) # FK
    
    sender_type = db.Column(db.String(20), nullable=False) # (EMS, HOSPITAL)
    # sender_ref_id는 team_id 또는 hospital_id의 String 값으로 저장 (ORM 관계는 설정하지 않음)
    sender_ref_id = db.Column(db.String(50), nullable=False) 
    
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(255), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self):
        return f"ChatMessage('{self.message_id}', Sender='{self.sender_type}')"
