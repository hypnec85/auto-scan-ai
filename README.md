# Auto Scan AI (오토 스캔: 중고차 분석 시스템)

**Auto Scan AI**는 중고차 매물의 수리 내역을 정밀 분석하여, **'보수적인 정비사'**의 관점에서 안전한 가성비 차량과 위험한 차량을 구분해주는 지능형 분석 시스템입니다.

엄격한 **규칙 기반(Rule-based) 필터링**과 **Google Gemini LLM**의 추론 능력을 결합하여, 단순 외판 교환(가성비)과 주요 골격 손상(위험)을 명확히 구분하고 최적의 구매 가이드를 제공합니다.

---

## 🚀 주요 기능 (Key Features)

### 1. 하이브리드 정밀 분석 (Hybrid Analysis Engine)
*   **1단계: 규칙 기반 필터링 (Rule-based Filtering)**
    *   `utils.py`에 내장된 정교한 키워드 매칭 알고리즘이 수리 내역 텍스트를 파싱합니다.
    *   **Tier 1 [절대 구매 금지]**: 휠하우스, 사이드 멤버, 필러 등 주요 골격(구조) 손상 차량을 즉시 식별합니다.
    *   **Tier 2 [주의 요망]**: 인사이드 패널, 리어 프레임 등 2차 구조적 손상 가능성이 있는 차량을 분류합니다.
    *   **Tier 3 [가성비 보석]**: 문, 후드, 휀더 등 단순 외판 교환 차량을 식별하여 '안전한 감가 매물'로 추천합니다.
    *   **Tier 0 [무사고]**: 수리 이력이 없는 깔끔한 차량을 분류합니다.

*   **2단계: AI 엔지니어 리포트 (Gemini LLM Powered)**
    *   필터링된 데이터를 Google Gemini에 전송하여 종합 리포트를 생성합니다.
    *   사용자가 선택한 우선순위(예: '안전 제일', '가성비 중심')에 맞춰 **Best 3** 및 **Worst 3** 차량을 선정하고, 그 이유를 상세히 설명합니다.

### 2. 유연한 데이터 입력 (Data Input)
*   **CSV 파일 업로드**: 다량의 매물 데이터를 한 번에 분석할 수 있습니다.
*   **수동 입력 지원**: 개별 매물의 정보를 직접 입력하여 즉석에서 분석할 수 있습니다.

### 3. 직관적인 시각화 (Visualization)
*   Streamlit 기반의 웹 UI를 통해 분석 결과를 표와 리포트 형태로 깔끔하게 제공합니다.

---

## 🛠 기술 스택 (Tech Stack)

*   **Language**: Python 3.10+
*   **Frontend**: Streamlit
*   **LLM**: Google Gemini (via `google-generativeai`)
*   **Data Processing**: Pandas, Regular Expressions (Regex)

---

## 📦 설치 및 실행 방법 (Installation & Usage)

### 1. 저장소 클론 (Clone Repository)
```bash
git clone https://github.com/hypnec85/auto-scan-ai.git
cd auto-scan-ai
```

### 2. 가상환경 설정 (Virtual Environment)
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 패키지 설치 (Install Dependencies)
```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정 (.env)
프로젝트 루트 경로에 `.env` 파일을 생성하고 Google Gemini API Key를 입력하세요.
```env
GOOGLE_API_KEY=your_api_key_here
```

### 5. 애플리케이션 실행 (Run Application)
```bash
streamlit run app.py
```

---

## 📂 프로젝트 구조 (Project Structure)

```
auto-scan-ai/
├── app.py                  # Streamlit 메인 애플리케이션 (UI 및 상태 관리)
├── utils.py                # 핵심 로직 (데이터 파싱, Tier 분류, LLM 통신)
├── tier_system.txt         # 사고 이력 등급 분류 기준 문서
├── project_plan.txt        # 프로젝트 기획 명세서
├── sample_data.csv         # 테스트용 샘플 데이터
├── requirements.txt        # Python 패키지 의존성 리스트
└── README.md               # 프로젝트 설명 문서
```

---

## 📝 라이선스 (License)

This project is licensed under the MIT License.
