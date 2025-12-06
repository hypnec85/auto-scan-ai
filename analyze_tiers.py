import pandas as pd
import utils
import sys

# Load data
try:
    df = utils.load_data('sample_data.csv')
except Exception as e:
    print(f"Error loading data: {e}")
    sys.exit(1)

# Apply tier system
# The categorize_car function returns a Series with [Tier, Reasons]
# We need to apply it to the dataframe
df[['Tier', 'Analysis']] = df.apply(utils.categorize_car, axis=1)

# Convert '내차피해액' to numeric for analysis
def parse_damage(x):
    if pd.isna(x) or x == '': return 0
    if isinstance(x, (int, float)): return x
    # Check for "미확정"
    if "미확정" in str(x): return -1 # Use -1 for undetermined
    try:
        return int(str(x).replace(',', ''))
    except:
        return 0

df['Damage_Num'] = df['내차피해액'].apply(parse_damage)

print("=== Tier Distribution ===")
print(df['Tier'].value_counts().sort_index())
print("\n")

print("=== Tier 1 Examples (Worst) ===")
tier1 = df[df['Tier'] == 1]
if not tier1.empty:
    print(tier1[['수리내역', '내차피해액']].head(10).to_string())
else:
    print("No Tier 1 cars found.")
print("\n")

print("=== Tier 2 Examples (Warning) ===")
tier2 = df[df['Tier'] == 2]
if not tier2.empty:
    print(tier2[['수리내역', '내차피해액']].head(10).to_string())
else:
    print("No Tier 2 cars found.")
print("\n")

print("=== Tier 3 Examples (Simple Repair) ===")
tier3 = df[df['Tier'] == 3]
if not tier3.empty:
    # Show those with highest damage amounts to check if they are really "simple"
    print(tier3.sort_values('Damage_Num', ascending=False)[['수리내역', '내차피해액']].head(10).to_string())
else:
    print("No Tier 3 cars found.")
print("\n")

print("=== Tier 0 Examples (Clean) ===")
tier0 = df[df['Tier'] == 0]
if not tier0.empty:
    # Show those with highest damage amounts (should be 0 or low if logic is correct, but logic says >0 damage becomes Tier 2...)
    # Wait, logic says: "If Tier 0 and not repair_text.strip() and own_damage_amount > 0: tier = 2"
    # So Tier 0 should have 0 damage. Let's verify.
    print(tier0.sort_values('Damage_Num', ascending=False)[['수리내역', '내차피해액']].head(10).to_string())
else:
    print("No Tier 0 cars found.")
print("\n")

print("=== High Damage Check (> 5,000,000 KRW) in Tier 2/3 ===")
high_damage = df[(df['Damage_Num'] > 5000000) & (df['Tier'].isin([2, 3]))]
if not high_damage.empty:
    print(high_damage[['Tier', '수리내역', '내차피해액']].to_string())
else:
    print("No high damage cars in Tier 2/3.")
