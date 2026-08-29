import { SecurityCheckResult, InputSource } from '../src/types';

describe('Types', () => {
  test('SecurityCheckResult should have required properties', () => {
    const result: SecurityCheckResult = {
      score: 85,
      riskLevel: 'low',
      recommendation: 'download',
      reasons: [],
      details: {
        maliciousPatterns: [],
        sensitiveDataAccess: [],
        destructiveBehavior: [],
        networkSuspicious: [],
        stars: 100,
        forks: 10,
        createdAt: '2020-01-01',
        lastUpdated: '2024-01-01',
        contributors: 5,
        isOfficial: false
      }
    };
    expect(result.score).toBe(85);
    expect(result.riskLevel).toBe('low');
  });
});
