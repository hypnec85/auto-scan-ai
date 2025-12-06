import pandas as pd

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
        '사이드실패널', '사이드실 패널', '사이드실',
        '쇽업소버', '쇼바', '댐퍼',
        '로우암', '로워암', '컨트롤 암'
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

def get_row_signature(row):
    """행 데이터를 기반으로 고유 시그니처 생성 (중복 방지 및 식별용)"""
    # 식별에 사용할 주요 컬럼들
    cols = ['차량명', '차량가격(만원)', '주행거리(km)', '연식', '최초 등록일', '수리내역']
    sig_parts = []
    for c in cols:
        val = row.get(c, '')
        sig_parts.append(str(val))
    return "_".join(sig_parts)