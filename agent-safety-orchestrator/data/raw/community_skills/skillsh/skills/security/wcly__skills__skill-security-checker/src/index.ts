import { SecurityCheckResult, CheckOptions, StaticAnalysisResult, RepoReputationResult, OutputFormat } from './types';
import { parseInput, ParsedSource } from './inputParser';
import { cloneRepo } from './repoManager';
import { runStaticAnalysis } from './staticAnalyzer';
import { getRepoReputation } from './repoReputation';
import { generateReport } from './reporter';
import { monitorRuntime } from './runtimeMonitor';

export async function checkSecurity(options: CheckOptions): Promise<SecurityCheckResult> {
  const source = parseInput(options.input);
  const repoPath = await cloneRepo(source);
  
  const staticAnalysis = await runStaticAnalysis(repoPath);
  const reputation = await getRepoReputation(source);
  
  let runtimeBehavior = null;
  if (options.enableRuntimeCheck) {
    runtimeBehavior = await monitorRuntime(repoPath);
  }
  
  const result = calculateResult(staticAnalysis, reputation, runtimeBehavior);
  return result;
}

function calculateSeverityScore(severity: string, confidence: string | undefined): number {
  const severityWeight = { high: 20, medium: 10, low: 5 };
  const confidenceWeight = { high: 1.0, medium: 0.6, low: 0.3 };
  
  const sev = severityWeight[severity as keyof typeof severityWeight] || 10;
  const conf = confidenceWeight[confidence as keyof typeof confidenceWeight] || 0.5;
  
  return Math.round(sev * conf);
}

function calculateResult(
  staticAnalysis: StaticAnalysisResult,
  reputation: RepoReputationResult,
  runtimeBehavior?: any
): SecurityCheckResult {
  let score = 100;
  let totalPatterns = 0;

  const patternCategories = [
    staticAnalysis.maliciousPatterns,
    staticAnalysis.sensitiveDataAccess,
    staticAnalysis.destructiveBehavior,
    staticAnalysis.networkSuspicious
  ];

  for (const patterns of patternCategories) {
    for (const pattern of patterns) {
      const deduction = calculateSeverityScore(pattern.severity, pattern.confidence);
      score -= deduction;
      totalPatterns++;
    }
  }

  if (runtimeBehavior) {
    if (runtimeBehavior.dangerousScripts && runtimeBehavior.dangerousScripts.length > 0) {
      score -= runtimeBehavior.dangerousScripts.length * 15;
    }
    if (runtimeBehavior.suspiciousFileAccess && runtimeBehavior.suspiciousFileAccess.length > 0) {
      score -= runtimeBehavior.suspiciousFileAccess.length * 10;
    }
    if (runtimeBehavior.networkConnections && runtimeBehavior.networkConnections.length > 0) {
      score -= runtimeBehavior.networkConnections.length * 10;
    }
  }

  const repoScore = calculateRepoScore(reputation);
  score += repoScore;

  score = Math.max(0, Math.min(100, score));

  const riskLevel = calculateRiskLevel(score, totalPatterns, staticAnalysis);
  const recommendation = calculateRecommendation(score, riskLevel, staticAnalysis);

  const reasons: string[] = generateReasons(staticAnalysis, reputation, runtimeBehavior);

  return {
    score,
    riskLevel,
    recommendation,
    reasons,
    details: {
      ...staticAnalysis,
      ...reputation,
      runtimeBehavior: runtimeBehavior || undefined
    }
  };
}

function calculateRepoScore(reputation: RepoReputationResult): number {
  let score = 0;
  
  if (reputation.stars > 10000) score += 20;
  else if (reputation.stars > 1000) score += 15;
  else if (reputation.stars > 100) score += 10;
  else if (reputation.stars > 10) score += 5;
  
  if (reputation.forks > 1000) score += 10;
  else if (reputation.forks > 100) score += 5;
  else if (reputation.forks > 10) score += 2;
  
  if (reputation.contributors > 100) score += 10;
  else if (reputation.contributors > 20) score += 7;
  else if (reputation.contributors > 5) score += 4;
  else if (reputation.contributors > 1) score += 2;
  
  if (reputation.isOfficial) score += 10;
  
  const createdDate = new Date(reputation.createdAt);
  const now = new Date();
  const ageInYears = (now.getTime() - createdDate.getTime()) / (1000 * 60 * 60 * 24 * 365);
  if (ageInYears > 5) score += 5;
  else if (ageInYears > 2) score += 3;
  else if (ageInYears > 1) score += 1;
  
  return score;
}

function calculateRiskLevel(
  score: number, 
  totalPatterns: number, 
  staticAnalysis: StaticAnalysisResult
): 'high' | 'medium' | 'low' {
  const highConfidenceMalicious = staticAnalysis.maliciousPatterns.filter(
    p => p.severity === 'high' && p.confidence === 'high'
  ).length;
  
  if (highConfidenceMalicious > 0 || score < 30) {
    return 'high';
  }
  
  if (totalPatterns > 10 || score < 50) {
    return 'medium';
  }
  
  return 'low';
}

function calculateRecommendation(
  score: number, 
  riskLevel: 'high' | 'medium' | 'low',
  staticAnalysis: StaticAnalysisResult
): 'download' | 'not_recommended' {
  const highConfidenceThreats = staticAnalysis.maliciousPatterns.filter(
    p => p.severity === 'high' && p.confidence === 'high'
  ).length;
  
  if (highConfidenceThreats > 0) {
    return 'not_recommended';
  }
  
  if (riskLevel === 'high' || score < 40) {
    return 'not_recommended';
  }
  
  if (riskLevel === 'medium' && score < 60) {
    return 'not_recommended';
  }
  
  return 'download';
}

function generateReasons(
  staticAnalysis: StaticAnalysisResult,
  reputation: RepoReputationResult,
  runtimeBehavior?: any
): string[] {
  const reasons: string[] = [];
  
  const highConfidenceMalicious = staticAnalysis.maliciousPatterns.filter(
    p => p.confidence === 'high'
  );
  if (highConfidenceMalicious.length > 0) {
    reasons.push(`检测到 ${highConfidenceMalicious.length} 个高置信度恶意代码模式`);
  }
  
  const highSeveritySensitive = staticAnalysis.sensitiveDataAccess.filter(
    p => p.severity === 'high' && p.confidence !== 'low'
  );
  if (highSeveritySensitive.length > 0) {
    reasons.push(`检测到 ${highSeveritySensitive.length} 个高风险敏感数据访问`);
  }
  
  if (staticAnalysis.destructiveBehavior.length > 0) {
    reasons.push(`检测到 ${staticAnalysis.destructiveBehavior.length} 个破坏性行为`);
  }
  
  if (runtimeBehavior && runtimeBehavior.dangerousScripts && runtimeBehavior.dangerousScripts.length > 0) {
    reasons.push(`检测到 ${runtimeBehavior.dangerousScripts.length} 个危险脚本`);
  }
  
  if (reputation.stars < 10 && reputation.contributors < 2) {
    reasons.push('仓库缺乏足够的社会监督（stars 和贡献者较少）');
  }
  
  if (reputation.stars > 1000) {
    reasons.push(`仓库有良好的社区支持（${reputation.stars} stars）`);
  }
  
  if (reputation.isOfficial) {
    reasons.push('仓库被识别为官方仓库');
  }
  
  return reasons;
}

export { generateReport } from './reporter';
export { SecurityCheckResult, CheckOptions, OutputFormat } from './types';
