import streamlit as st
import pandas as pd
import re
import os
import google.generativeai as genai
from dotenv import load_dotenv
import time
from datetime import datetime
import pickle
import uuid
import glob

# 환경 변수 로드 (API 키)
load_dotenv(override=True)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# 모델은 초기화 시도 전에는 None으로 설정
model_global = None 

if GOOGLE_API_KEY:
    print(f"DEBUG: API Key Loaded: {GOOGLE_API_KEY[:10]}... (Length: {len(GOOGLE_API_KEY)})")
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("Warning: GOOGLE_API_KEY not found in .env file. AI features will be disabled.")

# --- 세션 데이터 관리 함수 ---
def get_session_id():
    """
    현재 사용자의 고유 세션 ID를 생성하거나 가져옵니다.
    Streamlit의 query_params를 활용하여 브라우저 새로고침 시에도 세션 ID를 유지합니다.
    """
    if "session_id" in st.query_params:
        return st.query_params["session_id"]
    else:
        new_session_id = str(uuid.uuid4())
        st.query_params["session_id"] = new_session_id
        return new_session_id

def save_session_data(session_id, df, deleted_rows):
    """현재 세션의 데이터(DataFrame, 삭제 이력)를 서버의 임시 파일로 저장합니다."""
    try:
        filename = f"temp_data_{session_id}.pkl"
        data_to_save = {
            'df': df,
            'deleted_rows': deleted_rows,
            'timestamp': time.time()
        }
        with open(filename, 'wb') as f:
            pickle.dump(data_to_save, f)
        # print(f"Session data saved: {filename}") # 디버깅용
    except Exception as e:
        print(f"Error saving session data: {e}")

def load_session_data(session_id):
    """저장된 세션 데이터를 불러옵니다."""
    filename = f"temp_data_{session_id}.pkl"
    if os.path.exists(filename):
        try:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
            # print(f"Session data loaded: {filename}") # 디버깅용
            return data
        except Exception as e:
            print(f"Error loading session data: {e}")
            return None
    return None

def clear_session_data(session_id):
    """저장된 세션 파일을 삭제합니다."""
    filename = f"temp_data_{session_id}.pkl"
    if os.path.exists(filename):
        try:
            os.remove(filename)
            # print(f"Session data cleared: {filename}") # 디버깅용
        except Exception as e:
            print(f"Error clearing session data: {e}")

def cleanup_old_sessions(max_age_seconds=3600):
    """오래된(예: 1시간 이상 지난) 세션 파일을 정리합니다."""
    try:
        now = time.time()
        for filename in glob.glob("temp_data_*.pkl"):
            if os.path.getmtime(filename) < now - max_age_seconds:
                os.remove(filename)
                print(f"Old session file removed: {filename}")
    except Exception as e:
        print(f"Error cleaning up old sessions: {e}")


def load_data(file_path):
    """
    CSV 파일을 로드하고 필요한 전처리를 수행합니다.
    """
    try:
        # Streamlit uploaded_file_manager.UploadedFile 객체는 StringIO처럼 동작
        if isinstance(file_path, str):
            df = pd.read_csv(file_path)
        else: # BytesIO 또는 유사 객체
            df = pd.read_csv(file_path)
        # 수리내역 결측치는 빈 문자열로 처리
        df['수리내역'] = df['수리내역'].fillna('')
        # '옵션' 컬럼이 없는 경우 빈 문자열로 초기화
        if '옵션' not in df.columns:
            df['옵션'] = ''
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def parse_repair_history(repair_text, own_damage_amount=0): # 내차피해액도 인자로 받도록 수정
    """
    수리내역 텍스트를 분석하여 사고 등급(Tier)과 상세 사유를 반환합니다.
    '미확정' 키워드 및 내차피해액에 따른 위험도를 반영합니다.
    
    Returns:
        tier (int): 1 (Worst), 2 (Warning), 3 (Value), 0 (Clean)
        reasons (list): 등급 판정 사유 리스트
    """
    repair_text = str(repair_text) # 혹시 숫자가 들어올 경우 대비
    
    # 내차피해액 전처리
    own_damage_val = 0
    is_undetermined = False

    if isinstance(own_damage_amount, (int, float)):
        own_damage_val = int(own_damage_amount)
    else:
        s_val = str(own_damage_amount).strip()
        if "미확정" in s_val:
            is_undetermined = True
        else:
            try:
                own_damage_val = int(s_val.replace(',', ''))
            except ValueError:
                own_damage_val = 0

    tier = 0
    reasons = []
    
    # 미확정 키워드 확인 (초반에 우선적으로 처리)
    if "미확정" in repair_text:
        tier = max(tier, 2) # 미확정은 최소 Tier 2 경고
        reasons.append("미확정 수리내역 존재 (불확실성으로 인한 잠재적 위험)")
    
    # 내차피해액 확인
    if is_undetermined:
        tier = max(tier, 2)
        reasons.append("내차피해액 미확정 (불확실성으로 인한 잠재적 위험)")
    elif own_damage_val > 0 and not repair_text.strip():
        # 피해액은 있는데 수리내역이 없으면 애매하므로 경고
        tier = max(tier, 2)
        reasons.append(f"내차피해액 {own_damage_val}원 발생 (수리내역 미상)")


    # Tier 1: 주요 골격 (절대 구매 금지)
    # 휠하우스, 사이드멤버, 필러, 대쉬패널, 플로어패널
    tier1_keywords = [
        '휠하우스', '사이드멤버', '필러패널', '대쉬패널', '플로어패널',
        '휠 하우스', '사이드 멤버', '필러 패널', '대쉬 패널', '플로어 패널'
    ]
    
    # Tier 2: 주요 골격 (경고)
    # 인사이드패널, 프론트패널, 크로스멤버, 트렁크플로어, 리어패널, 패키지트레이, 루프패널, 쿼터패널, 사이드실패널
    tier2_keywords = [
        '인사이드패널', '프론트패널', '크로스멤버', '트렁크플로어', '리어패널', '패키지트레이',
        '루프패널', '쿼터패널', '사이드실패널', '인사이드 패널', '프론트 패널', '크로스 멤버',
        '트렁크 플로어', '리어 패널', '패키지 트레이', '루프 패널', '쿼터 패널', '사이드실 패널'
    ]
    
    # Tier 3: 외판 단순 교환 (감가 매력)
    # 후드, 휀더, 도어, 트렁크리드, 라디에이터서포터
    tier3_keywords = [
        '후드', '프론트휀더', '프론트 휀더', '도어', '트렁크리드', '트렁크 리드', '라디에이터서포터', '라디에이터 서포터'
    ]

    # 교환(X), 판금/용접(W) 키워드 확인
    
    # Tier 1 Check
    for keyword in tier1_keywords:
        if keyword in repair_text:
            tier = max(tier, 1)
            reasons.append(f"Tier 1 위험 부위 손상: {keyword}")

    # Tier 2 Check (Tier 1이 아닐 때만 등급 결정, 사유는 추가)
    for keyword in tier2_keywords:
        if keyword in repair_text:
            if tier == 0 or tier > 2: # 현재 등급보다 더 심각한 경우 업데이트 (Tier 1은 덮어쓰지 않음)
                 if tier == 0: tier = 2
            reasons.append(f"Tier 2 경고 부위 손상: {keyword}")

    # Tier 3 Check
    for keyword in tier3_keywords:
        if keyword in repair_text:
            # Tier 1, 2가 발견되지 않았거나 (최소 Tier 3 이상일 경우만 업데이트)
            if tier == 0:
                tier = 3
            reasons.append(f"Tier 3 단순 교환/수리: {keyword}")
            
    # 최종적으로 Tier가 0 (무사고)인데 수리내역이 있는 경우 Tier 3 처리 (기타 수리)
    if tier == 0 and repair_text.strip():
        tier = 3
        reasons.append("기타 수리 내역 존재 (상세 확인 필요)")
    elif tier == 0 and not repair_text.strip() and own_damage_amount == 0:
         reasons.append("무사고") # 확실한 무사고
    elif tier == 0 and not repair_text.strip() and own_damage_amount > 0:
         tier = 2 # 수리내역은 없지만 피해액이 있는 경우 경고
         reasons.append(f"내차피해액 {own_damage_amount}원 발생 (수리내역 미상, 추가 확인 필요)")

    # 중복 제거 및 최종 Tier 확정
    final_reasons = []
    [final_reasons.append(x) for x in reasons if x not in final_reasons]

    # reasons가 비어있고 tier가 0이 아니면, default 이유를 추가
    if not final_reasons and tier != 0:
        if tier == 1: final_reasons.append("Tier 1 (심각한 구조 손상)")
        elif tier == 2: final_reasons.append("Tier 2 (경고: 잠재적 위험)")
        elif tier == 3: final_reasons.append("Tier 3 (단순 수리)")
    elif not final_reasons and tier == 0:
        final_reasons.append("무사고 (수리내역 및 피해액 없음)")


    return tier, ", ".join(final_reasons) if final_reasons else "무사고"


def categorize_car(row):
    # 내차피해액 컬럼도 parse_repair_history에 전달
    tier, reasons = parse_repair_history(row['수리내역'], row['내차피해액'])
    return pd.Series([tier, reasons])

def generate_engineer_report(df, user_preference):
    """
    Gemini API를 사용하여 엔지니어 관점의 분석 리포트를 생성합니다.
    모델 폴백 메커니즘을 적용하여 API 오류 시 다음 모델을 시도합니다.
    """
    if GOOGLE_API_KEY is None:
        return "API 키가 설정되지 않아 AI 분석을 수행할 수 없습니다.", None

    # 사용 가능한 모델 리스트 (우선순위 순)
    # models.txt 기반
    model_candidates = [
        'gemini-2.5-pro',
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-2.0-flash-lite'
    ]

    # 현재 날짜
    current_date = datetime.now()

    # 프롬프트에 넣을 데이터 요약 (옵션, 특수용도이력, 색상, 1인소유 컬럼 추가)
    # 필요한 컬럼이 있는지 확인하고 가져오기
    cols_to_use = ['차량명', '엔진', '트림', '차량가격(만원)', '주행거리(km)', '연식', '최초 등록일', '색상', '특수용도이력', '1인소유', '옵션', '수리내역', '내차피해액', 'Tier', '분석결과']
    # 실제 존재하는 컬럼만 필터링
    cols_to_use = [c for c in cols_to_use if c in df.columns]
    
    summary_df = df[cols_to_use].copy()
    
    # 차량 경과 개월 수 계산
    def calculate_months(reg_date_str):
        try:
            reg_date = pd.to_datetime(reg_date_str)
            # 날짜 형식이 잘못되었거나 NaT인 경우 처리
            if pd.isna(reg_date):
                return "Unknown"
            return (current_date.year - reg_date.year) * 12 + (current_date.month - reg_date.month)
        except:
            return "Unknown"

    if '최초 등록일' in summary_df.columns:
        summary_df['경과개월수'] = summary_df['최초 등록일'].apply(calculate_months)
    else:
        summary_df['경과개월수'] = "Unknown"

    # 숫자만 있으면 LLM이 혼동할 수 있으므로 단위를 붙여 문자열로 변환
    if '차량가격(만원)' in summary_df.columns:
        summary_df['차량가격(만원)'] = summary_df['차량가격(만원)'].astype(str) + "만원"
    if '주행거리(km)' in summary_df.columns:
        summary_df['주행거리(km)'] = summary_df['주행거리(km)'].astype(str) + "km"
    if '내차피해액' in summary_df.columns:
        summary_df['내차피해액'] = summary_df['내차피해액'].astype(str) + "원"
    
    # 컬럼명 영문 변환 (LLM 인식 용이성)
    col_map = {
        '차량명': 'Model', '엔진': 'Engine', '트림': 'Trim', '차량가격(만원)': 'Price', 
        '주행거리(km)': 'Mileage', '연식': 'Model Year', '최초 등록일': 'Registration Date',
        '색상': 'Color', '특수용도이력': 'Special Use', '1인소유': 'Single Owner', '옵션': 'Option', 
        '수리내역': 'Repair History', '내차피해액': 'Own Damage Amount', 
        'Tier': 'Safety Tier', '분석결과': 'Analysis Summary', '경과개월수': 'Age(Months)'
    }
    summary_df = summary_df.rename(columns=col_map)
    
    data_str = summary_df.to_markdown()

    prompt = f"""
    당신은 보수적이고 깐깐한 기계 공학자 출신의 중고차 전문가입니다. 
    다음 제공된 중고차 목록 데이터를 분석하여 구매자에게 리포트를 작성해 주세요.

    **현재 날짜:** {current_date.strftime('%Y년 %m월 %d일')}

    **데이터 특성 및 평가 가이드:**
    1. **Special Use (특수용도이력)**: 'O'인 경우 렌터카, 리스, 영업용 이력이 있다는 뜻입니다. 
       - 이는 다수의 운전자가 험하게 몰았을 가능성(관리 상태 불량)이 높으므로 감가 요인이 되며, 보수적으로 평가해야 합니다.
    2. **Color (색상)**: 한국 중고차 시장에서는 **흰색, 검은색**이 가장 선호도가 높고 감가 방어에 유리합니다. 그 다음은 **은색/쥐색** 계열이며, **유채색(빨강, 파랑 등)**은 선호도가 낮아 감가가 큽니다. 이를 가성비 판단에 참고하십시오.
    3. **Mileage vs Age (주행거리와 연식)**: 
       - 'Age(Months)'는 최초 등록일로부터 현재까지의 경과 개월 수입니다.
       - 단순히 주행거리가 짧다고 좋은 차가 아닙니다. 예를 들어, 1년에 1~2만km가 적정 주행거리입니다.
       - 연식 대비 주행거리가 너무 짧으면(장기 방치, 시내 주행 위주) 엔진 상태가 나쁠 수 있고, 너무 길면(택시, 영업용 등 혹사) 부품 마모가 심할 수 있습니다.
       - 예: "경과개월수 24개월에 100,000km"는 극심한 혹사 차량으로 평가해야 합니다. 반면 "60개월에 100,000km"는 정상적인 운행입니다.
    4. **Single Owner (1인소유)**:
       - 'O' (1인소유)인 경우 관리 상태가 양호할 가능성이 높아 시장에서 선호합니다(플러스 요인).
       - 'X' (소유자 변경)라고 해서 큰 문제가 있는 것은 아니지만, 1인소유 차량에 가산점을 부여하십시오.
    5. **Option (옵션)**: 편의성에 큰 영향을 주며, 가성비 평가의 중요 요소입니다.
    6. **Uncertainty (미확정)**: 'Repair History'나 'Own Damage Amount'에 **"미확정"** 키워드가 있다면 잠재적 위험이 매우 큽니다 (최소 Tier 2).

    **사용자 분석 성향:** {user_preference}

    **분석 기준:**
    1. **안전이 최우선**: 'Safety Tier'가 1인 차량은 절대 추천하지 않으며, 'Worst'로 분류해야 합니다.
    2. **가성비 (Value for Money)**: 'Safety Tier'가 3인 차량 중 'Mileage', 'Price', 'Option', 'Color', 'Special Use', 'Single Owner'를 종합적으로 고려해 선정합니다.
       - 특수용도이력이 없고, 1인소유이며, 인기 색상(흰/검)이고, 연식 대비 주행거리가 적절한 차가 베스트입니다.
    3. **사용자 성향 반영**: "{user_preference}"에 맞춰 Top 3와 Worst 3를 선정하십시오.
    4. **정중한 태도**: 기계 공학적 지식을 바탕으로 하되, **모든 문장은 반드시 정중한 경어체(하십시오체 또는 해요체)를 사용하십시오.**

    **요청 사항:**
    - **Top 3 추천 차량**: 가성비가 가장 훌륭한 차량 3대 선정 (원본 데이터의 인덱스 번호 포함). 추천 이유 상세 기술.
    - **Worst 3 경고 차량**: 가장 위험하고 돈 낭비인 차량 3대 선정 (원본 데이터의 인덱스 번호 포함). 비추천 이유 상세 기술.
    - 데이터:
    {data_str}

    **출력 형식:**
    # 🛠️ 엔지니어의 픽: Top 3 가성비 매물
    1. **[N번] 차종 (가격 / 주행거리 / 색상)**
       - 💡 선정 이유: ... (경어체 사용)
    
    # 🚨 엔지니어의 경고: 절대 사면 안 되는 매물 (Worst 3)
    1. **[N번] 차종 (가격 / 주행거리 / 색상)**
       - ⚠️ 위험 요소: ... (경어체 사용)
    
    # 📝 총평
    ... (경어체 사용)
    """

    last_error = None
    for model_name in model_candidates:
        try:
            # 모델 초기화 시 오류 발생 방지를 위해 여기에 모델 생성 로직을 넣음
            model_instance = genai.GenerativeModel(model_name)
            response = model_instance.generate_content(prompt)
            return response.text, model_name # 성공 시 리포트와 모델명 반환
        except Exception as e:
            print(f"Warning: Failed with {model_name}. Error: {e}")
            last_error = e
            time.sleep(1) # 잠시 대기 후 재시도
            continue
    
    # 모든 모델 실패 시 (항상 튜플을 반환하도록 수정)
    return f"AI 분석 중 모든 모델에서 오류가 발생했습니다. 마지막 오류: {str(last_error)}", None