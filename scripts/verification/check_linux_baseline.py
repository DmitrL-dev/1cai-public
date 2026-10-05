"""Gate new Linux failures without pretending the Windows-oriented suite is green."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def assess(junit, baseline, pytest_exit):
    cases = list(ET.parse(junit).getroot().iter('testcase'))
    known = {row['test'] for row in json.loads(Path(baseline).read_text())['tests']}
    identities = [case.attrib.get('classname', '') + '::' + case.attrib.get('name', '')
                  for case in cases]
    failed = sorted(identity for identity, case in zip(identities, cases)
                    if case.find('failure') is not None or case.find('error') is not None)
    counts = {key: sum(case.find(tag) is not None for case in cases)
              for key, tag in [('failed', 'failure'), ('errors', 'error'), ('skipped', 'skipped')]}
    counts['passed'] = len(cases) - sum(counts.values())
    unexpected = sorted(set(failed) - known)
    missing = sorted(known - set(identities))
    consistent = (pytest_exit == (1 if failed else 0)
                  and len(set(identities)) == len(identities)
                  and all(sum(case.find(tag) is not None for tag in ('failure', 'error', 'skipped')) <= 1
                          for case in cases))
    accepted = (consistent and len(cases) >= 3000 and counts['passed'] >= 2000
                and not unexpected and not missing)
    return {
        'schema': 1, 'scope': 'Linux diagnostic baseline comparison; not full product qualification',
        'counts': counts, 'pytest_exit': pytest_exit, 'new_failures': unexpected,
        'report_consistent': consistent, 'missing_baseline_cases': missing,
        'known_failures_present': failed, 'known_failures_absent': sorted(known - set(failed)),
        'full_suite_green': accepted and not failed,
        'baseline_comparison_passed': accepted,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--junit', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--pytest-exit', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = assess(args.junit, args.baseline, args.pytest_exit)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('scope', 'counts', 'new_failures', 'full_suite_green', 'baseline_comparison_passed')}))
    return 0 if report['baseline_comparison_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
