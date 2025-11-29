# Project Context: 오토 스캔: 중고차 분석 시스템 (Auto Scan AI)

## Overview
This directory contains the planning documents and initial datasets for the **"오토 스캔: 중고차 분석 시스템 (Auto Scan AI)"** project. 

The goal is to build a web service that allows users to upload a CSV of used car listings. The system will then use an LLM (Gemini) to analyze the data from a **"conservative mechanical engineer's"** perspective, distinguishing between safe, value-for-money vehicles (cosmetic damage only) and dangerous vehicles (structural damage).

## Directory Contents

### Core Planning Documents
*   **`project_plan.txt`**: The comprehensive project specification.
    *   **Objective**: Identify Top 3 (Best Value) and Worst 3 (Dangerous) cars from a list.
    *   **Tech Stack**: Python + Streamlit (Planned).
    *   **Key Logic**: Differentiate between cosmetic depreciation and safety hazards.
*   **`tier_system.txt`**: The core classification logic for accident history.
    *   **Tier 1 [Do Not Buy]**: Structural damage (Wheel house, Side member, Pillars). 
    *   **Tier 2 [Warning]**: Inner panels, rear frame damage.
    *   **Tier 3 [Value Gem]**: Simple bolt-on external parts (Doors, Hood, Fenders). These are "good" because they lower the price without affecting safety.
*   **`car_parts.txt`**: A reference list of specific car parts, categorized by "Outer Panel" (Weban) and "Major Skeleton" (Golgyeok), used for parsing the repair history.

### Datasets
*   **`중고차(20251128).csv`**: A sample raw dataset containing used car listings.
    *   **Key Columns**: 
        *   `수리내역`: Text description of repairs (e.g., "프론트휀더(우)(교환)"). This is the primary input for the logic.
        *   `차량가격(만원)`, `주행거리(km)`, `연식`: Quantitative metrics for evaluation.
        *   `내차피해액`, `내차피해횟수`: Auxiliary safety metrics.

## Planned Architecture
1.  **Frontend**: Python + Streamlit for easy CSV upload and interactive filtering.
2.  **Processing**: 
    *   **Rule-based Filtering**: Parse text in `수리내역` against `tier_system.txt` to flag "Red Flag" cars immediately.
    *   **LLM Analysis**: Send filtered data to Gemini to generate the "Engineer's Commentary" and final ranking.
3.  **Output**: A report showing the best and worst deals with detailed reasoning.

## Development Conventions (Planned)
*   **Language**: Python (for data processing and backend logic).
*   **Data Handling**: `pandas` for CSV manipulation.
*   **Prompt Engineering**: The LLM persona must be strict, conservative, and focused on mechanical safety.
