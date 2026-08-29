#!/usr/bin/env python3
# Cross-border Compliance Framework - handler.py
# Pure descriptive skill. No code execution, API calls, or network access.
import json, re

SKILL_INFO = {'name': 'Cross-border Compliance Framework', 'slug': 'cb-compliance-framework', 'version': '1.0.0'}

COMPLIANCE_DB = {
    'Germany': {
        'tax': {'vat_rate': '19% (7% reduced)', 'registration': 'Required if storing goods in Germany or exceeding 100k EUR cross-border sales'},
        'consumer_protection': {'cooling_off': '14 days', 'lang_req': 'German required for AGB/Impressum', 'key_regs': ['TMG Impressum requirement', 'BGB withdrawal rights', 'Distance Selling Act']},
        'data_privacy': {'framework': 'GDPR + BDSG', 'key_req': ['DPO required if >20 employees processing data', 'Privacy policy in German']},
        'product_safety': {'marks': ['CE', 'GS mark (optional)'], 'regs': ['ProdSG (Product Safety Act)', 'ElektroG (WEEE)', 'BattG (Battery Act)']},
        'customs': {'tariff_threshold': '150 EUR de minimis', 'documents': ['Commercial invoice', 'Packing list', 'EUR1 for preferential origin']}},
    'France': {
        'tax': {'vat_rate': '20% (5.5% reduced)', 'registration': 'Required for B2C sales to France (OSS scheme available)'},
        'consumer_protection': {'cooling_off': '14 days', 'lang_req': 'French required for all customer-facing content', 'key_regs': ['French Consumer Code', 'Loi Hamon']},
        'data_privacy': {'framework': 'GDPR + Loi Informatique et Libertes', 'key_req': ['CNIL registration', 'Data breach notification 72h']},
        'product_safety': {'marks': ['CE', 'NF mark'], 'regs': ['French Decree on product safety', 'REACH compliance']},
        'customs': {'tariff_threshold': '150 EUR', 'documents': ['Commercial invoice FR', 'Packing list', 'SAS/SARL registration']}},
    'Japan': {
        'tax': {'vat_rate': '10% (8% reduced)', 'registration': 'Required if annual turnover exceeds 10M JPY'},
        'consumer_protection': {'cooling_off': '8 days (specified goods)', 'lang_req': 'Japanese required for contracts', 'key_regs': ['Consumer Contract Act', 'Specified Commercial Transactions Act']},
        'data_privacy': {'framework': 'APPI (Amended 2022)', 'key_req': ['PSCB registration', 'Cross-border transfer consent']},
        'product_safety': {'marks': ['PSE (electrical)', 'SG (general products)'], 'regs': ['Electrical Appliance and Material Safety Act', 'Food Sanitation Act (if applicable)']},
        'customs': {'tariff_threshold': '10000 JPY', 'documents': ['Commercial invoice', 'Packing list', 'Certificate of origin']}},
    'Australia': {
        'tax': {'vat_rate': '10% GST', 'registration': 'ABN required for GST registration (75k AUD threshold)'},
        'consumer_protection': {'cooling_off': '10 days (some goods)', 'lang_req': 'English', 'key_regs': ['Australian Consumer Law (ACL)', 'Competition and Consumer Act']},
        'data_privacy': {'framework': 'Privacy Act 1988 (APP)', 'key_req': ['APP compliance', 'Data breach notification']},
        'product_safety': {'marks': ['RCM', 'AS/NZS standards'], 'regs': ['ACCC product safety', 'Competition and Consumer Act']},
        'customs': {'tariff_threshold': '1000 AUD', 'documents': ['Commercial invoice', 'Packing list', 'Certificate of origin']}},
    'UK': {
        'tax': {'vat_rate': '20% (5% reduced)', 'registration': 'HMRC VAT registration required above 85k GBP threshold'},
        'consumer_protection': {'cooling_off': '14 days', 'lang_req': 'English', 'key_regs': ['Consumer Rights Act 2015', 'Consumer Contracts Regulations']},
        'data_privacy': {'framework': 'UK GDPR + DPA 2018', 'key_req': ['ICO registration', 'UK Representative for non-UK businesses']},
        'product_safety': {'marks': ['UKCA (replaces CE from 2025)'], 'regs': ['UK Product Safety and Metrology Regulations']},
        'customs': {'tariff_threshold': '135 GBP', 'documents': ['Customs declarations (post-Brexit)', 'Commercial invoice', 'Certificate of origin']}},
}

CATEGORY_REQS = {
    'electronics': ['CE/RED compliance', 'WEEE registration', 'Battery directive', 'RoHS compliance'],
    'apparel': ['Textile labeling', 'REACH compliance (chemicals)', 'Care symbols'],
    'beauty': ['Cosmetics regulation (EU 1223/2009)', 'Animal testing ban compliance', 'INCI labeling'],
}

def _parse_input(user_input):
    inp = user_input.lower()
    p = {'original_input': user_input[:100], 'word_count': len(user_input.split())}
    found = [m for m in COMPLIANCE_DB if m.lower() in inp]
    p['target_markets'] = found[:5] if found else list(COMPLIANCE_DB.keys())[:3]
    cats = []
    for cat, terms in [('electronics',['electronics','electronic','tech']),('apparel',['apparel','clothing','fashion']),
                       ('beauty',['beauty','cosmetics','skincare'])]:
        if any(t in inp for t in terms): cats.append(cat)
    p['product_categories'] = cats or ['general_merchandise']
    p['activities'] = ['online_retail']
    return p

def _compliance_map(markets, categories):
    result = {}
    for m in markets:
        if m not in COMPLIANCE_DB: continue
        data = COMPLIANCE_DB[m]
        entry = {
            'market': m,
            'tax_requirements': {'vat_rate': data['tax']['vat_rate'], 'registration': data['tax']['registration']},
            'consumer_protection': {'cooling_off_period': data['consumer_protection']['cooling_off'],
                                    'language_requirements': data['consumer_protection']['lang_req'],
                                    'key_regulations': data['consumer_protection']['key_regs']},
            'data_privacy': {'framework': data['data_privacy']['framework'], 'requirements': data['data_privacy']['key_req']},
            'product_safety': {'required_marks': data['product_safety']['marks'], 'regulations': data['product_safety']['regs']}}
        cat_items = []
        for c in categories:
            if c in CATEGORY_REQS: cat_items.extend(CATEGORY_REQS[c])
        if cat_items: entry['category_specific_requirements'] = list(set(cat_items))
        result[m] = entry
    return result

def _roadmap():
    return {'compliance_roadmap': [
        {'phase': 'Immediate (0-1 month)', 'actions': ['Identify all applicable regulations per target market', 'Register for VAT/GST in primary markets', 'Engage local legal counsel', 'Conduct GDPR readiness assessment']},
        {'phase': 'Short-term (1-3 months)', 'actions': ['Implement data privacy compliance', 'Set up product safety marking', 'Create market-compliant terms', 'Configure tax calculation system']},
        {'phase': 'Ongoing', 'actions': ['Monitor regulatory changes quarterly', 'Renew certifications', 'Maintain compliance documentation repository']}]}

def _doc_framework(markets):
    return {'documentation_framework': [
        {'market': m, 'required_documents': ['Terms and Conditions (local language)', 'Privacy Policy (local language)',
                                             'Impressum/About page', 'Returns/Refund policy', 'Commercial invoice template',
                                             'Product safety documentation']} for m in markets]}

def _pro_recommendations(markets):
    recs = {}
    for m in markets:
        specialists = ['International Tax Advisor', 'Data Privacy Consultant']
        if m in ['Germany', 'France']: specialists.append('EU Regulatory Compliance Attorney')
        if m in ['Japan']: specialists.append('Japan METI Regulatory Specialist')
        if m in ['UK', 'Australia']: specialists.append('International Trade Lawyer')
        recs[m] = list(set(specialists))
    return {'recommended_professionals': recs}

def handle(user_input):
    parsed = _parse_input(user_input)
    return json.dumps({
        'skill': SKILL_INFO['slug'], 'name': SKILL_INFO['name'],
        'input_analysis': parsed,
        'compliance_requirements': _compliance_map(parsed['target_markets'], parsed['product_categories']),
        'implementation_roadmap': _roadmap(),
        'compliance_documentation_framework': _doc_framework(parsed['target_markets']),
        'professional_consultation_recommendations': _pro_recommendations(parsed['target_markets']),
        'disclaimer': 'Descriptive guidance only. Not professional legal, tax, or compliance advice. Always verify with qualified legal counsel before implementation.',
    }, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    for t in ['what compliance do I need for selling electronics in Germany and France',
              'help me understand regulations for shipping apparel to Japan and Australia',
              'regulations for cross-border sales to UK']:
        p = json.loads(handle(t))
        assert 'compliance_requirements' in p and 'implementation_roadmap' in p
        assert 'disclaimer' in p
        print('  PASS: ' + t[:50])
    print('All self-tests passed!')
