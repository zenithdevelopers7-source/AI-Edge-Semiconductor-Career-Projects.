"""Compare two offline EDGEOPS baselines on identical synthetic holdout rows.

This command does not load production data, update the dashboard database,
write model binaries, connect hardware or deploy a classifier. With --output,
it saves immutable synthetic comparison reports for offline dashboard review.
"""
import json
import argparse
from run_offline_experiment import synthetic_fixture
from sklearn_comparison import compare_same_holdout

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Save immutable comparison JSON for dashboard review")
    args = parser.parse_args()
    if args.output:
        from comparison_registry import save_comparison
        saved = save_comparison(synthetic_fixture(), args.output)
        result = {"comparison_id": saved["comparison_id"], **saved["report"]["result"]}
    else:
        result = compare_same_holdout(synthetic_fixture())
    print(json.dumps(result, indent=2, sort_keys=True))
