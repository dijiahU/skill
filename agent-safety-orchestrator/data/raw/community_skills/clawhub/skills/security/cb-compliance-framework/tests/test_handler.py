#!/usr/bin/env python3
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from handler import handle

CASES = [
    {'name': 'test_electronics_de_fr', 'input': 'what compliance do I need for selling electronics in Germany and France',
     'checks': [lambda p: 'compliance_requirements' in p, lambda p: len(p['compliance_requirements'])>=2,
                lambda p: 'implementation_roadmap' in p, lambda p: 'disclaimer' in p]},
    {'name': 'test_apparel_jp_au', 'input': 'help me understand regulations for shipping apparel to Japan and Australia',
     'checks': [lambda p: 'compliance_requirements' in p, lambda p: 'professional_consultation_recommendations' in p,
                lambda p: 'disclaimer' in p]},
    {'name': 'test_uk', 'input': 'regulations for cross-border sales to UK with electronics',
     'checks': [lambda p: 'compliance_requirements' in p, lambda p: 'compliance_documentation_framework' in p,
                lambda p: 'disclaimer' in p]},
    {'name': 'test_empty', 'input': '',
     'checks': [lambda p: isinstance(p,dict), lambda p: 'skill' in p, lambda p: 'disclaimer' in p]},
]

if __name__ == '__main__':
    print('cb-compliance-framework tests')
    print('='*50)
    passed = 0
    for tc in CASES:
        try: p = json.loads(handle(tc['input']))
        except Exception as e: print('  FAIL ' + tc['name'] + ': ' + str(e)); continue
        failed = [c.__name__ for c in tc['checks'] if not c(p)]
        if failed: print('  FAIL ' + tc['name'] + ': ' + str(failed))
        else: print('  PASS ' + tc['name']); passed += 1
    print(f'\n{passed}/{len(CASES)} tests passed.')
    if passed == len(CASES): print('All tests passed!')
    else: sys.exit(1)
