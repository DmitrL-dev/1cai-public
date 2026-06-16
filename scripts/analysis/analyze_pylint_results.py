"""
Analyze pylint results and categorize issues by type
"""
import json
from collections import Counter

# Read pylint results
with open('pylint_final_check.json', 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

print("=" * 80)
print("PYLINT RESULTS ANALYSIS")
print("=" * 80)
print(f"\nTotal issues: {len(data)}\n")

# Group by message-id
by_message_id = Counter(item.get('message-id', 'unknown') for item in data)

print("Top 20 issue types:")
print("-" * 80)
print(f"{'Message ID':<20} {'Count':>10} {'Type':<15}")
print("-" * 80)

for msg_id, count in by_message_id.most_common(20):
    # Get type from first occurrence
    issue_type = next((item.get('type', 'unknown') for item in data if item.get('message-id') == msg_id), 'unknown')
    print(f"{msg_id:<20} {count:>10} {issue_type:<15}")

print("\n" + "=" * 80)
print("SUMMARY BY TYPE")
print("=" * 80)

by_type = Counter(item.get('type', 'unknown') for item in data)
for issue_type, count in by_type.most_common():
    print(f"{issue_type:<20} {count:>10}")

print("\n" + "=" * 80)
print("AUTO-FIXABLE CATEGORIES")
print("=" * 80)

# Categorize by fixability
auto_fixable = {
    'C0301': 'Line too long',
    'C0303': 'Trailing whitespace',
    'W0611': 'Unused import',
    'W0612': 'Unused variable',
    'W0613': 'Unused argument',
    'C0411': 'Wrong import order',
    'C0412': 'Ungrouped imports',
    'C0413': 'Wrong import position',
    'W1203': 'Lazy logging',
    'C0114': 'Missing module docstring',
    'C0115': 'Missing class docstring',
    'C0116': 'Missing function docstring',
}

semi_auto = {
    'R0913': 'Too many arguments',
    'R0914': 'Too many locals',
    'R0912': 'Too many branches',
    'R0915': 'Too complex',
    'R0801': 'Duplicate code',
}

auto_count = sum(count for msg_id, count in by_message_id.items() if msg_id in auto_fixable)
semi_count = sum(count for msg_id, count in by_message_id.items() if msg_id in semi_auto)
manual_count = len(data) - auto_count - semi_count

print(f"\nAuto-fixable:     {auto_count:>6} ({auto_count/len(data)*100:.1f}%)")
print(f"Semi-automated:   {semi_count:>6} ({semi_count/len(data)*100:.1f}%)")
print(f"Manual review:    {manual_count:>6} ({manual_count/len(data)*100:.1f}%)")

print("\n" + "=" * 80)
print("AUTO-FIXABLE BREAKDOWN")
print("=" * 80)

for msg_id, description in auto_fixable.items():
    count = by_message_id.get(msg_id, 0)
    if count > 0:
        print(f"{msg_id:<10} {description:<30} {count:>6}")

print("\n" + "=" * 80)

# Save detailed breakdown
breakdown = {
    'total': len(data),
    'auto_fixable': auto_count,
    'semi_automated': semi_count,
    'manual': manual_count,
    'by_message_id': dict(by_message_id.most_common(50)),
    'by_type': dict(by_type),
}

with open('pylint_analysis_breakdown.json', 'w', encoding='utf-8') as f:
    json.dump(breakdown, f, indent=2)

print("\n✅ Analysis saved to: pylint_analysis_breakdown.json")
