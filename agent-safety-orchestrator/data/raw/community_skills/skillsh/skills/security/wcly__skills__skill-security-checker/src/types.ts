export interface SecurityCheckResult {
  score: number;
  riskLevel: 'high' | 'medium' | 'low';
  recommendation: 'download' | 'not_recommended';
  reasons: string[];
  details: StaticAnalysisResult & RepoReputationResult & { runtimeBehavior?: RuntimeBehaviorResult };
}

export interface StaticAnalysisResult {
  maliciousPatterns: PatternMatch[];
  sensitiveDataAccess: PatternMatch[];
  destructiveBehavior: PatternMatch[];
  networkSuspicious: PatternMatch[];
}

export interface PatternMatch {
  file: string;
  line: number;
  code: string;
  description: string;
  severity: 'high' | 'medium' | 'low';
  confidence?: 'high' | 'medium' | 'low';
}

export interface RepoReputationResult {
  stars: number;
  forks: number;
  createdAt: string;
  lastUpdated: string;
  contributors: number;
  isOfficial: boolean;
}

export interface RuntimeBehaviorResult {
  dangerousScripts: string[];
  suspiciousFileAccess: string[];
  networkConnections: string[];
}

export interface InputSource {
  type: 'github' | 'local' | 'npm';
  path: string;
}

export type OutputFormat = 'json' | 'friendly' | 'concise';

export interface CheckOptions {
  input: InputSource;
  outputFormat: OutputFormat;
  enableRuntimeCheck: boolean;
}
