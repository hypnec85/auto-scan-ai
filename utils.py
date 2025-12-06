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

def parse_repair_history(repair_text, own_damage_amount=0):
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
    
    # 1. 불확실성 체크 (미확정, 확인불가 등)
    uncertainty_keywords = ["미확정", "확인불가", "확인 불가", "세부내역 없음", "정보 없음", "내역 없음"]
    for kw in uncertainty_keywords:
        if kw in repair_text:
            tier = max(tier, 2) # 정보 불확실성은 최소 Tier 2 경고
            reasons.append(f"정보 불확실성 경고 ({kw})")
    
    # 내차피해액 확인 (수리내역이 없는데 피해액만 큰 경우)
    if is_undetermined:
        tier = max(tier, 2)
        reasons.append("내차피해액 미확정 (불확실성으로 인한 잠재적 위험)")
    elif own_damage_val > 0 and not repair_text.strip():
        tier = max(tier, 2)
        reasons.append(f"내차피해액 {own_damage_val}원 발생 (수리내역 미상)")


    # --- Tier 분류 키워드 정의 (확장됨) ---

    # Tier 1: 주요 골격 (절대 구매 금지) - 차체 뼈대 손상
    # 주의: '플로어패널'은 '트렁크플로어'와 중복되므로 별도 로직으로 처리
    tier1_keywords = [
        '휠하우스', '휠 하우스',
        '사이드멤버', '사이드 멤버',
        '필러패널', '필러 패널', 'A필러', 'B필러', 'C필러', '센터필러',
        '대쉬패널', '대쉬 패널', '데쉬패널', '데쉬 패널', '대시패널',
        # 플로어패널은 별도 처리
    ]
    
    # Tier 2: 주요 골격 (경고) - 후방 골격 또는 볼트 체결이 아닌 용접 부위
    tier2_keywords = [
        '인사이드패널', '인사이드 패널',
        '프론트패널', '프론트 패널',
        '크로스멤버', '크로스 멤버',
        '트렁크플로어', '트렁크 플로어',
        '리어패널', '리어 패널', '백패널',
        '패키지트레이', '패키지 트레이',
        '루프패널', '루프 패널', '루프',
        '쿼터패널', '쿼터 패널', '뒤휀다', '뒤펜더', '리어펜더', '리어휀다',
        '사이드실패널', '사이드실 패널', '사이드실'
    ]
    
    # Tier 3: 외판 단순 교환 (감가 매력) - 볼트 체결 부품
    tier3_keywords = [
        '후드', '본네트', '보닛',
        '프론트휀더', '프론트 휀더', '앞휀다', '앞펜더', '프론트펜더',
        '도어', '앞문', '뒷문',
        '트렁크리드', '트렁크 리드', '트렁크',
        '라디에이터서포터', '라디에이터 서포터', '라디에이터 서포트'
    ]

    # --- 키워드 매칭 로직 ---

    # 1. Tier 1 Check (플로어패널 예외 처리 포함)
    for keyword in tier1_keywords:
        if keyword in repair_text:
            tier = max(tier, 1)
            reasons.append(f"Tier 1 위험 부위 손상: {keyword}")
            
    # 플로어패널 별도 체크 (트렁크플로어 오인 방지)
    if '플로어패널' in repair_text or '플로어 패널' in repair_text:
        # "트렁크" 또는 "리어"라는 단어가 바로 앞에 붙어있지 않은지 확인하는 것은 정규식이 정확하지만,
        # 간단하게 해당 텍스트에 '트렁크플로어패널'이 있으면 Tier 2로 처리하고,
        # '플로어패널'만 단독으로 있거나 다른 수식어면 Tier 1으로 의심해야 함.
        # 여기서는 보수적으로: '트렁크플로어'가 있으면 Tier 2 로직에서 잡히므로,
        # '플로어패널'이 있고 '트렁크'가 없는 경우만 Tier 1으로 간주.
        if '트렁크' not in repair_text and '리어' not in repair_text:
             tier = max(tier, 1)
             reasons.append("Tier 1 위험 부위 손상: 플로어패널")

    # 2. Tier 2 Check
    for keyword in tier2_keywords:
        if keyword in repair_text:
            # Tier 1이 이미 확정된 경우(tier=1)는 굳이 등급을 2로 내리지 않음
            # 현재 등급이 0이거나 3일 경우 -> 2로 격상
            # 현재 등급이 2일 경우 -> 유지
            if tier != 1:
                tier = 2
            reasons.append(f"Tier 2 경고 부위 손상: {keyword}")

    # 3. Tier 3 Check
    for keyword in tier3_keywords:
        if keyword in repair_text:
            # 상위 등급(1, 2)이 없을 때만 Tier 3 설정
            if tier == 0:
                tier = 3
            reasons.append(f"Tier 3 단순 교환/수리: {keyword}")
            
    # 4. 기타 처리
    # 최종적으로 Tier가 0 (무사고)인데 수리내역 텍스트가 있는 경우 -> Tier 3 (기타 수리)
    if tier == 0 and repair_text.strip():
        tier = 3
        reasons.append("기타 수리 내역 존재 (상세 확인 필요)")
    elif tier == 0 and not repair_text.strip() and own_damage_amount == 0:
         reasons.append("무사고")
    elif tier == 0 and not repair_text.strip() and own_damage_amount > 0:
         tier = 2 
         reasons.append(f"내차피해액 {own_damage_amount}원 발생 (수리내역 미상, 추가 확인 필요)")

    # 중복 제거 및 최종 Tier 확정
    final_reasons = []
    seen = set()
    for r in reasons:
        if r not in seen:
            final_reasons.append(r)
            seen.add(r)

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
    cols_to_use = [
        '차량명', '엔진', '트림', '차량가격(만원)', '주행거리(km)', '연식', '최초 등록일', 
        '색상', '특수용도이력', '1인소유', '옵션', '수리내역', '내차피해액', 'Tier', '분석결과',
        '일반부품보증기간(개월)', '일반부품보증거리(km)', '주요부품보증기간(개월)', '주요부품보증거리(km)'
    ]
    # 실제 존재하는 컬럼만 필터링
    cols_to_use = [c for c in cols_to_use if c in df.columns]
    
    summary_df = df[cols_to_use].copy()
    
    # 차량 경과 개월 수 계산
    def calculate_months(reg_date_str):
        try:
            reg_date = pd.to_datetime(reg_date_str)
            # 날짜 형식이 잘못되었거나 NaT인 경우 처리
            if pd.isna(reg_date):
                return None
            return (current_date.year - reg_date.year) * 12 + (current_date.month - reg_date.month)
        except:
            return None

    if '최초 등록일' in summary_df.columns:
        summary_df['경과개월수'] = summary_df['최초 등록일'].apply(calculate_months)
    else:
        summary_df['경과개월수'] = None

    # 잔여 보증 기간/거리 계산
    # 일반부품
    if '일반부품보증기간(개월)' in summary_df.columns and '경과개월수' in summary_df.columns:
        summary_df['잔여일반보증(개월)'] = summary_df.apply(
            lambda x: max(0, x['일반부품보증기간(개월)'] - x['경과개월수']) if x['경과개월수'] is not None else "Unknown", axis=1
        )
    if '일반부품보증거리(km)' in summary_df.columns and '주행거리(km)' in summary_df.columns:
        summary_df['잔여일반보증(km)'] = summary_df.apply(
            lambda x: max(0, x['일반부품보증거리(km)'] - x['주행거리(km)']), axis=1
        )
        
    # 주요부품
    if '주요부품보증기간(개월)' in summary_df.columns and '경과개월수' in summary_df.columns:
        summary_df['잔여주요보증(개월)'] = summary_df.apply(
            lambda x: max(0, x['주요부품보증기간(개월)'] - x['경과개월수']) if x['경과개월수'] is not None else "Unknown", axis=1
        )
    if '주요부품보증거리(km)' in summary_df.columns and '주행거리(km)' in summary_df.columns:
        summary_df['잔여주요보증(km)'] = summary_df.apply(
            lambda x: max(0, x['주요부품보증거리(km)'] - x['주행거리(km)']), axis=1
        )

    # 보증 만료 정책 적용: 기간이나 거리 중 하나라도 만료(0)되면 둘 다 만료 처리
    def sync_warranty_expiration(row, mon_col, km_col):
        rem_mon = row.get(mon_col)
        rem_km = row.get(km_col)
        
        # 날짜 정보가 없는 경우(Unknown) 처리
        if rem_mon == "Unknown":
            if rem_km == 0: # 거리가 만료되었으면 전체 만료
                return 0, 0
            return rem_mon, rem_km # 기간은 모르지만 거리는 남음 -> 유지
            
        # 둘 다 숫자인 경우
        try:
            if rem_mon <= 0 or rem_km <= 0:
                return 0, 0
        except:
            pass # 비교 불가능한 경우 패스
            
        return rem_mon, rem_km

    if '잔여일반보증(개월)' in summary_df.columns and '잔여일반보증(km)' in summary_df.columns:
        gen_res = summary_df.apply(lambda x: sync_warranty_expiration(x, '잔여일반보증(개월)', '잔여일반보증(km)'), axis=1, result_type='expand')
        summary_df['잔여일반보증(개월)'] = gen_res[0]
        summary_df['잔여일반보증(km)'] = gen_res[1]

    if '잔여주요보증(개월)' in summary_df.columns and '잔여주요보증(km)' in summary_df.columns:
        maj_res = summary_df.apply(lambda x: sync_warranty_expiration(x, '잔여주요보증(개월)', '잔여주요보증(km)'), axis=1, result_type='expand')
        summary_df['잔여주요보증(개월)'] = maj_res[0]
        summary_df['잔여주요보증(km)'] = maj_res[1]

    # 입력용 보증 컬럼은 LLM에게 혼동을 줄 수 있으므로 삭제하고 잔여량만 제공 (또는 둘 다 제공)
    # 리포트 작성에는 잔여량이 중요하므로 잔여량 위주로 컬럼 정리
    # 기존 입력값은 삭제 (깔끔한 표를 위해)
    drop_cols = ['일반부품보증기간(개월)', '일반부품보증거리(km)', '주요부품보증기간(개월)', '주요부품보증거리(km)']
    summary_df = summary_df.drop(columns=[c for c in drop_cols if c in summary_df.columns])

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
        'Tier': 'Safety Tier', '분석결과': 'Analysis Summary', '경과개월수': 'Age(Months)',
        '잔여일반보증(개월)': 'Rem. Gen Warranty(Mon)', '잔여일반보증(km)': 'Rem. Gen Warranty(Km)',
        '잔여주요보증(개월)': 'Rem. Major Warranty(Mon)', '잔여주요보증(km)': 'Rem. Major Warranty(Km)'
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
    4. **Warranty (보증 잔여)**:
       - **Rem. Gen Warranty (일반부품 보증)** 및 **Rem. Major Warranty (주요부품 보증)** 정보가 포함되어 있습니다.
       - 잔여 보증이 남아있는 경우 수리비 리스크를 줄여주므로 긍정적인 요소이며, 보증이 만료되었다면 그만큼 차량 가격이 합리적이어야 합니다.
       - **주의**: 보증 기간(개월)과 보증 거리(km) 중 하나라도 만료(0)되면 해당 보증은 완전히 만료된 것입니다.
    5. **Single Owner (1인소유)**: 'O' (1인소유)인 경우 관리 상태가 양호할 가능성이 높아 긍정적인 요소입니다.
    6. **Uncertainty (미확정)**: 'Repair History'나 'Own Damage Amount'에 "미확정" 키워드가 있다면 잠재적 위험이 큽니다.

    **사용자 분석 성향:** {user_preference}

    **분석 기준:**
    1. **안전이 최우선**: 'Safety Tier'가 1인 차량은 절대 추천하지 않으며, 'Worst'로 분류해야 합니다.
    2. **가성비 (Value for Money)**: 'Safety Tier'가 3인 차량 중 'Mileage', 'Price', 'Warranty', 'Option', 'Special Use', 'Single Owner' 등을 종합적으로 고려합니다. 각 요소의 중요도는 사용자 분석 성향에 따라 조절하십시오.
    3. **사용자 성향 반영**: "{user_preference}"에 맞춰 Top 3와 Worst 3를 선정하십시오.
    4. **정중한 태도**: 기계 공학적 지식을 바탕으로 하되, **모든 문장은 반드시 정중한 경어체(하십시오체 또는 해요체)를 사용하십시오.**

    **요청 사항:**
    - **Top 3 추천 차량**: 가성비 및 보증 혜택이 훌륭한 차량 3대 선정. 추천 이유 상세 기술.
    - **Worst 3 경고 차량**: 위험하고 가성비 나쁜 차량 3대 선정. 비추천 이유 상세 기술.
    - 데이터:
    {data_str}

    **출력 형식:**
    # 🛠️ 엔지니어의 픽: Top 3 가성비 매물
    1. **[N번] 차종 (가격 / 주행거리 / 색상)**
       - 💡 선정 이유: ...
    
    # 🚨 엔지니어의 경고: 절대 사면 안 되는 매물 (Worst 3)
    1. **[N번] 차종 (가격 / 주행거리 / 색상)**
       - ⚠️ 위험 요소: ...
    
    # 📝 총평
    ...
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