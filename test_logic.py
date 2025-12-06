import pandas as pd
from storage import load_data
from domain_logic import categorize_car

# 테스트할 CSV 파일 경로
CSV_FILE_PATH = 'sample_data.csv'

def run_logic_test():
    print(f"'{CSV_FILE_PATH}' 파일 로드 중...")
    df = load_data(CSV_FILE_PATH)

    if df is None:
        print(f"오류: '{CSV_FILE_PATH}' 파일을 로드할 수 없습니다. 파일 경로를 확인하거나 파일 내용을 점검하십시오.")
        return

    print("데이터 로드 성공. 수리내역 분석 중...")
    # categorize_car 함수는 Series를 반환하므로, apply와 함께 사용하여 DataFrame에 새 컬럼을 추가합니다.
    df[['사고등급', '사고원인']] = df.apply(categorize_car, axis=1)

    print("\n상위 5개 차량의 분석 결과:")
    print(df[['수리내역', '사고등급', '사고원인']].head().to_markdown(index=False))

    print("\n사고등급별 차량 개수:")
    print(df['사고등급'].value_counts().sort_index().to_markdown())

    print("\nTier 1 (절대 구매 금지) 차량:")
    tier1_cars = df[df['사고등급'] == 1]
    if not tier1_cars.empty:
        print(tier1_cars[['수리내역', '사고등급', '사고원인']].to_markdown(index=False))
    else:
        print("Tier 1 차량 없음.")

    print("\nTier 2 (경고) 차량:")
    tier2_cars = df[df['사고등급'] == 2]
    if not tier2_cars.empty:
        print(tier2_cars[['수리내역', '사고등급', '사고원인']].to_markdown(index=False))
    else:
        print("Tier 2 차량 없음.")
        
    print("\nTier 3 (단순 교환/수리) 차량:")
    tier3_cars = df[df['사고등급'] == 3]
    if not tier3_cars.empty:
        print(tier3_cars[['수리내역', '사고등급', '사고원인']].to_markdown(index=False))
    else:
        print("Tier 3 차량 없음.")

    print("\nTier 0 (무사고) 차량:")
    tier0_cars = df[df['사고등급'] == 0]
    if not tier0_cars.empty:
        print(tier0_cars[['수리내역', '사고등급', '사고원인']].to_markdown(index=False))
    else:
        print("Tier 0 차량 없음.")


if __name__ == "__main__":
    run_logic_test()
