import pandas as pd
import re
import os
import google.generativeai as genai
from dotenv import load_dotenv
import time

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

    # 프롬프트에 넣을 데이터 요약
    summary_df = df[['차량명', '엔진', '트림', '차량가격(만원)', '주행거리(km)', '연식', '수리내역', '내차피해액', 'Tier', '분석결과']].copy()
    
    # 숫자만 있으면 LLM이 혼동할 수 있으므로 단위를 붙여 문자열로 변환
    summary_df['차량가격(만원)'] = summary_df['차량가격(만원)'].astype(str) + "만원"
    summary_df['주행거리(km)'] = summary_df['주행거리(km)'].astype(str) + "km"
    summary_df['내차피해액'] = summary_df['내차피해액'].astype(str) + "원" 
    
    summary_df.columns = ['Model', 'Engine', 'Trim', 'Price', 'Mileage', 'Model Year', 'Repair History', 'Own Damage Amount', 'Safety Tier', 'Analysis Summary']
    
    data_str = summary_df.to_markdown()

    prompt = f"""
    당신은 보수적이고 깐깐한 기계 공학자 출신의 중고차 전문가입니다. 
    다음 제공된 중고차 목록 데이터를 분석하여 구매자에게 리포트를 작성해 주세요.

    **데이터 특성:**
    - 제공된 목록에는 서로 다른 차종(Model), 엔진(Engine), 트림(Trim)이 섞여 있을 수 있습니다.
    - 'Repair History'나 'Own Damage Amount'에 **"미확정"**이라는 키워드가 있다면, 이는 정보의 불확실성을 나타내므로 해당 차량은 잠재적 위험이 크다고 판단하여 보수적으로 평가해 주십시오. (최소 Tier 2 경고 수준)
    - 차종이 다르더라도 오직 '기계적 완성도', '안전성', '가성비' 관점에서 공정하게 평가해 주십시오.

    **사용자 분석 성향:** {user_preference}

    **분석 기준:**
    1. **안전이 최우선**: 'Safety Tier'가 1인 차량은 구조적 결함 가능성이 매우 높으므로 절대 추천하지 않으며, 'Worst'로 분류해야 합니다.
    2. **가성비 (Value for Money)**: 'Safety Tier'가 3인 차량 중 'Mileage'가 짧고 'Price'가 합리적인 차량은 "단순 교환으로 인한 감가" 차량으로 간주하여 'Top'으로 추천합니다. '무사고' 차량보다 가성비가 좋을 수 있습니다.
    3. **사용자 성향 반영**: 사용자의 '분석 성향'이 "{user_preference}"이므로, 이에 맞춰 Top 3와 Worst 3를 선정하고 코멘트를 작성해 주세요.
    4. **전문적이지만 정중한 태도**: 기계 공학적 지식(프레임, 휠하우스 등)을 바탕으로 명확한 근거를 제시하되, **모든 문장은 반드시 정중한 경어체(하십시오체 또는 해요체)를 사용하십시오.** 반말이나 하대는 절대 금지입니다.

    **요청 사항:**
    - **Top 3 추천 차량**: 가성비가 가장 훌륭한 차량 3대 선정 (원본 데이터의 인덱스 번호 포함). 추천 이유 상세 기술.
    - **Worst 3 경고 차량**: 가장 위험하고 돈 낭비인 차량 3대 선정 (원본 데이터의 인덱스 번호 포함). 비추천 이유 상세 기술.
    - 데이터:
    {data_str}

    **출력 형식:**
    # 🛠️ 엔지니어의 픽: Top 3 가성비 매물
    1. **[인덱스 N] 차종 (가격 / 주행거리)**
       - 💡 선정 이유: ... (경어체 사용)
    
    # 🚨 엔지니어의 경고: 절대 사면 안 되는 매물 (Worst 3)
    1. **[인덱스 N] 차종 (가격 / 주행거리)**
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
