import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import os

fake = Faker()
np.random.seed(42)

# --- Config ---
N_DEALS = 2000
N_REPS = 20
SEGMENTS = ['SMB', 'Mid-Market', 'Enterprise']
PRODUCTS = ['Core', 'Professional', 'Enterprise Suite']
DEAL_TYPES = ['New Business', 'Expansion', 'Renewal']
REJECTION_REASONS = [
    'Exceeds discount threshold',
    'Missing business case',
    'Below minimum ARR',
    'Competitor match unverified',
    'Margin too low'
]

# --- Reps ---
rep_ids = [f'REP_{str(i).zfill(3)}' for i in range(1, N_REPS + 1)]

# Some reps are over-discounters (top 5)
rep_discount_bias = {rep: np.random.uniform(0.05, 0.15) for rep in rep_ids}
for rep in rep_ids[:5]:  # over-discounters
    rep_discount_bias[rep] = np.random.uniform(0.18, 0.30)

# --- Segment ARR ranges ---
segment_arr = {
    'SMB':         (5_000,  30_000),
    'Mid-Market':  (30_000, 150_000),
    'Enterprise':  (150_000, 800_000)
}

# --- Segment discount norms ---
segment_discount_mean = {
    'SMB':        0.08,
    'Mid-Market': 0.13,
    'Enterprise': 0.20
}

# --- Generate deals ---
deals = []
start_date = datetime(2024, 1, 1)

for i in range(1, N_DEALS + 1):
    segment = np.random.choice(SEGMENTS, p=[0.45, 0.35, 0.20])
    rep_id = np.random.choice(rep_ids)
    arr_min, arr_max = segment_arr[segment]
    list_price = np.random.randint(arr_min, arr_max)
    deal_type = np.random.choice(DEAL_TYPES, p=[0.50, 0.30, 0.20])
    product = np.random.choice(PRODUCTS, p=[0.40, 0.35, 0.25])

    # Deal type discount adjustment
    deal_type_discount_adj = {
        'New Business': 0.00,
        'Expansion':   -0.02,
        'Renewal':     -0.04
    }[deal_type]

    # Discount: blend segment norm + rep bias + deal type
    base_discount = segment_discount_mean[segment]
    rep_bias = rep_discount_bias[rep_id]
    discount_pct = np.clip(
        np.random.normal(
            loc=(base_discount + rep_bias) / 2 + deal_type_discount_adj,
            scale=0.05
        ),
        0.0, 0.50
    )

    deals.append({
        'deal_id':      f'DEAL_{str(i).zfill(4)}',
        'rep_id':       rep_id,
        'account_id':   f'ACC_{str(np.random.randint(1, 1201)).zfill(4)}',
        'segment':      segment,
        'arr':          list_price,
        'list_price':   list_price,
        'discount_pct': round(discount_pct, 4),
        'deal_type':    deal_type,
        'product':      product,
        'created_date': (
            start_date + timedelta(days=np.random.randint(0, 365))
        ).date()
    })

deals_df = pd.DataFrame(deals)

# --- Generate approvals ---
thresholds = {'SMB': 0.10, 'Mid-Market': 0.15, 'Enterprise': 0.20}
deals_df['threshold'] = deals_df['segment'].map(thresholds)
deals_df['needs_approval'] = deals_df['discount_pct'] > deals_df['threshold']

approvals = []
approval_id = 1

for _, deal in deals_df[deals_df['needs_approval']].iterrows():
    submitted_date = deal['created_date'] + timedelta(
        days=np.random.randint(1, 5)
    )

    base_days = {'SMB': 2, 'Mid-Market': 4, 'Enterprise': 8}[deal['segment']]
    cycle_days = max(1, int(np.random.normal(base_days, base_days * 0.4)))
    decision_date = submitted_date + timedelta(days=cycle_days)

    reject_prob = np.clip(
        (deal['discount_pct'] - deal['threshold']) * 3, 0.05, 0.60
    )
    status = np.random.choice(
        ['Approved', 'Rejected', 'Pending'],
        p=[1 - reject_prob - 0.05, reject_prob, 0.05]
    )

    rejection_reason = (
        np.random.choice(REJECTION_REASONS) if status == 'Rejected' else None
    )

    approvals.append({
        'approval_id':      f'APR_{str(approval_id).zfill(4)}',
        'deal_id':          deal['deal_id'],
        'approver':         np.random.choice(['VP Sales', 'CFO', 'CRO']),
        'submitted_date':   submitted_date,
        'decision_date':    decision_date if status != 'Pending' else None,
        'cycle_days':       cycle_days if status != 'Pending' else None,
        'status':           status,
        'rejection_reason': rejection_reason
    })
    approval_id += 1

approvals_df = pd.DataFrame(approvals)

# --- Generate outcomes ---
outcomes = []

for _, deal in deals_df.iterrows():
    # Base win rate by segment
    base_win = {
        'SMB': 0.55, 'Mid-Market': 0.45, 'Enterprise': 0.35
    }[deal['segment']]

    # Deal type adjustment
    deal_type_adj = {
        'New Business': 0.00,
        'Expansion':    0.15,
        'Renewal':      0.25
    }[deal['deal_type']]

    # Discount elasticity
    discount = deal['discount_pct']
    if discount < 0.05:
        win_adj = -0.05
    elif discount < 0.15:
        win_adj = 0.05
    elif discount < 0.25:
        win_adj = 0.0
    else:
        win_adj = -0.10

    win_prob = np.clip(
        base_win + deal_type_adj + win_adj + np.random.normal(0, 0.05),
        0.05, 0.95
    )
    win_flag = int(np.random.random() < win_prob)

    close_date = deal['created_date'] + timedelta(
        days=np.random.randint(14, 120)
    )
    final_arr = (
        round(deal['list_price'] * (1 - deal['discount_pct']), 2)
        if win_flag else 0.0
    )

    outcomes.append({
        'deal_id':    deal['deal_id'],
        'stage':      'Closed Won' if win_flag else 'Closed Lost',
        'close_date': close_date,
        'win_flag':   win_flag,
        'final_arr':  final_arr
    })

outcomes_df = pd.DataFrame(outcomes)

# --- Clean up helper cols ---
deals_df = deals_df.drop(columns=['threshold', 'needs_approval'])

# --- Save ---
os.makedirs('data/raw', exist_ok=True)
deals_df.to_csv('data/raw/deals.csv', index=False)
approvals_df.to_csv('data/raw/approvals.csv', index=False)
outcomes_df.to_csv('data/raw/outcomes.csv', index=False)

print(f"deals:     {len(deals_df):,} rows")
print(f"approvals: {len(approvals_df):,} rows")
print(f"outcomes:  {len(outcomes_df):,} rows")
print(f"\nOver-discounting reps: {rep_ids[:5]}")
print(
    f"\nDeals needing approval: "
    f"{deals_df['discount_pct'].gt(deals_df.apply(lambda r: thresholds[r['segment']], axis=1)).sum():,}"
)