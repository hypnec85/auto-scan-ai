# 🏗️ Auto Scan AI: Architecture & Technical Deep Dive

이 문서는 **Auto Scan AI**의 내부 작동 원리, 핵심 알고리즘, 그리고 AI 통합 전략을 상세히 설명합니다. 

---

## 1. 시스템 아키텍처 (System Architecture)

Auto Scan AI는 **하이브리드 접근 방식(Hybrid Approach)**을 채택했습니다. 100% AI에 의존하지 않고, 명확한 규칙(Rule-based)으로 1차 필터링을 거친 후, AI가 정성적인 분석을 수행하는 구조입니다.

```mermaid
graph TD
    A[User Input (CSV / Form)] --> B(Data Preprocessing);
    B --> C{Rule-based Engine};
    C -->|Keyword Matching| D[Tier Classification];
    D -->|Tier 1: Critical| E[Tag: Worst];
    D -->|Tier 3: Cosmetic| F[Tag: Best Value];
    
    E & F --> G(Prompt Engineering);
    G -->|Context + Data| H[Google Gemini LLM];
    H --> I[Engineer Report];
    I --> J[Streamlit UI];
```

---

## 2. Tier 분류 시스템 (Rule-based Logic)

LLM은 때때로 사실이 아닌 정보를 생성(Hallucination)할 수 있습니다. 자동차의 **구조적 안전**과 관련된 문제는 0.1%의 오류도 허용될 수 없으므로, `utils.py` 내에 **정규표현식 기반의 엄격한 분류 로직**을 구현했습니다.

### Tier 1: 절대 구매 금지 (Structural Damage)
자동차의 뼈대(프레임)가 손상된 차량입니다. 수리를 완벽하게 해도 주행 안정성이 떨어질 수 있습니다.
*   **Keywords**: `휠하우스`, `사이드멤버`, `필러패널`, `대쉬패널`, `플로어패널`
*   **Action**: 무조건 '위험'으로 분류하고 경고 메시지 출력.

### Tier 2: 경고 (Potential Risk)
주요 골격과 연결된 2차 구조물이 손상되었거나, 정보가 불확실한 경우입니다.
*   **Keywords**: `리어패널`, `인사이드패널`, `크로스멤버`, `미확정(수리비용/내역)`
*   **Action**: 주의 요망 상태로 분류.

### Tier 3: 가성비 추천 (Cosmetic Repairs)
볼트로 체결된 단순 외판 부품만 교환된 경우입니다. 성능에는 지장이 없으나 중고차 시장에서는 사고차로 분류되어 가격이 저렴해지므로, **최고의 가성비 매물**이 됩니다.
*   **Keywords**: `후드`, `프론트휀더`, `도어`, `트렁크리드`
*   **Action**: 안전 등급 '양호'로 분류 및 추천.

---

## 3. Generative AI 통합 (Gemini API)

규칙 기반 엔진이 "안전성"을 담보한다면, **Gemini LLM**은 "구매 조언"과 "가치 평가"를 담당합니다.

### 3.1 프롬프트 엔지니어링 (Prompt Engineering)
LLM에게 단순한 요약이 아닌, **페르소나(Persona)**를 부여하여 결과물의 톤앤매너를 조절했습니다.

*   **Persona**: "보수적이고 깐깐한 기계 공학자 출신의 중고차 전문가"
*   **Context Injection**: 
    *   단순 숫자가 아닌 의미 단위로 데이터를 변환하여 주입합니다. (예: `2150` -> `2150만원`)
    *   **Dynamic Date Calculation**: Python에서 현재 날짜와 최초 등록일을 비교하여 계산한 '경과 개월 수'를 프롬프트에 직접 주입합니다. 이를 통해 LLM이 "연식 대비 주행거리(혹사 여부)"를 정확히 판단합니다.
    *   **Market Logic**: '특수용도이력(렌트/리스)' 여부, '색상', '1인소유' 정보를 추가하여, 한국 중고차 시장의 실제 감가 및 프리미엄 요인을 분석에 반영했습니다.
    *   '옵션(Option)' 데이터의 중요성을 명시하여, 풀옵션 차량의 가성비를 높게 평가하도록 유도했습니다.
*   **Safety Rails**: "반말 금지", "정중한 경어체 사용", "Tier 1 차량 추천 금지" 등의 제약 조건을 프롬프트에 명시했습니다.

### 3.2 모델 폴백 메커니즘 (Model Fallback)
서비스 안정성을 위해 하나의 모델에만 의존하지 않습니다. API 호출 실패 시 자동으로 다음 모델을 시도합니다.

1.  **Priority 1**: `gemini-2.5-pro` (최고 성능, 복잡한 추론)
2.  **Priority 2**: `gemini-2.5-flash` (속도 최적화)
3.  **Priority 3**: `gemini-2.0-flash` (안정적인 구형 모델)

---

## 4. 데이터 처리 (Data Processing)

*   **유연한 입력**: `app.py`는 CSV 업로드뿐만 아니라 Python `pandas`를 활용한 동적 폼 입력을 지원합니다.
*   **결측치 처리**: 중고차 데이터 특성상 누락된 정보(옵션, 수리내역 등)가 많으므로, 이를 안전한 기본값(`Empty String`, `0`)으로 치환하여 로직 오류를 방지했습니다.
