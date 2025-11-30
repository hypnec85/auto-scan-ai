# 🚗 Auto Scan AI (오토 스캔)

> **"이 차, 사도 될까요?"**
> 보수적인 정비 엔지니어의 시각으로 중고차 성능점검기록부를 정밀 분석해주는 AI 어시스턴트

![License](https://img.shields.io/badge/license-MIT-green) ![Python](https://img.shields.io/badge/python-3.10-blue) ![Streamlit](https://img.shields.io/badge/streamlit-1.31-red) ![Gemini](https://img.shields.io/badge/AI-Gemini_Pro-orange)

---

## 🧐 프로젝트 배경 (Why This Project?)

중고차를 구매할 때 가장 큰 장벽은 **"정보의 비대칭성"**입니다. 
딜러가 제공하는 **성능점검기록부**에는 '프론트 휀더 교환', '사이드 멤버 판금' 같은 전문 용어가 가득하지만, 일반인은 이것이 단순한 접촉 사고인지, 생명을 위협하는 대형 사고인지 구분하기 어렵습니다.

**Auto Scan AI**는 이러한 문제를 해결하기 위해 개발되었습니다. 
단순히 데이터를 보여주는 것을 넘어, **"20년 경력의 보수적인 정비소 사장님"**이라면 이 차를 추천할지, 아니면 뜯어말릴지를 AI가 판단해줍니다.

---

## 💡 핵심 기능 (Key Features)

### 1. 하이브리드 정밀 분석 (Hybrid Analysis Engine)
LLM(대규모 언어 모델)의 환각(Hallucination) 현상을 방지하고 정확도를 높이기 위해 **규칙 기반(Rule-based) 필터링**과 **Generative AI**를 결합했습니다.

*   **Tier 1 [구매 금지 🛑]**: 휠하우스, 사이드 멤버 등 주요 골격(뼈대) 손상 차량을 즉시 걸러냅니다.
*   **Tier 2 [주의 요망 ⚠️]**: 리어 패널, 인사이드 패널 등 2차 골격 손상이나 내차 피해액 미확정 차량을 경고합니다.
*   **Tier 3 [가성비 추천 ✅]**: 문, 후드, 휀더 등 **단순 외판 교환** 차량은 안전에 지장이 없으면서 감가상각이 많이 되어 최고의 가성비 매물로 추천합니다.

### 2. AI 엔지니어 리포트 (AI Engineer Report)
구글의 **Gemini Pro** 모델을 활용하여, 딱딱한 데이터가 아닌 **사람이 이해하기 쉬운 리포트**를 제공합니다.
*   사용자의 성향(안전 우선 vs 가성비 우선)에 맞춰 추천/비추천 차량을 선정합니다.
*   옵션 정보(내비게이션, 선루프 등)를 고려하여 가격 대비 가치를 평가합니다.

### 3. 직관적인 시각화
*   Streamlit 기반의 웹 UI로 CSV 파일을 업로드하거나 직접 정보를 입력하여 즉시 분석할 수 있습니다.

---

## 🛠️ 기술 스택 (Tech Stack)

*   **Language**: Python 3.10
*   **Web Framework**: Streamlit
*   **AI Model**: Google Gemini (via `google-generativeai` SDK)
*   **Data Processing**: Pandas, Regular Expressions (Regex)

---

## 🚀 설치 및 실행 (Installation & Usage)

이 프로젝트를 로컬 환경에서 실행하려면 다음 단계에 따라주세요.

### 1. 저장소 클론 (Clone)
```bash
git clone https://github.com/hypnec85/auto-scan-ai.git
cd auto-scan-ai
```

### 2. 가상환경 생성 및 활성화
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 패키지 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정 (.env)
프로젝트 루트 경로에 `.env` 파일을 생성하고 Google Gemini API Key를 입력하세요. ([API 키 발급받기](https://aistudio.google.com/app/apikey))
```env
GOOGLE_API_KEY=your_api_key_here
```

### 5. 앱 실행
```bash
streamlit run app.py
```

---

## 📂 프로젝트 구조 (Project Structure)

*   `app.py`: Streamlit 애플리케이션의 메인 엔트리 포인트. UI 구성 및 상태 관리를 담당합니다.
*   `utils.py`: 핵심 비즈니스 로직이 담긴 파일입니다. 데이터 파싱, Tier 분류 알고리즘, Gemini API 연동 코드가 포함되어 있습니다.
*   `tier_system.txt`: 차량 손상 부위에 따른 위험도 분류 기준(Tier 1~3)을 정의한 문서입니다.
*   `ARCHITECTURE.md`: 시스템의 상세 설계 및 AI 프롬프트 엔지니어링 전략을 다루는 기술 문서입니다.

---

## 📜 라이선스 (License)

이 프로젝트는 [MIT License](LICENSE)를 따릅니다. 자유롭게 수정하고 배포하셔도 됩니다.