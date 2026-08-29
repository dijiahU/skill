import * as fs from 'fs';
import * as path from 'path';
import { glob } from 'glob';
import { StaticAnalysisResult, PatternMatch } from './types';
import { detectionRules, checkSafePath, shouldExclude } from './detectionPatterns';

export async function runStaticAnalysis(repoPath: string): Promise<StaticAnalysisResult> {
  const files = await glob('**/*.{js,ts,py,sh,rb}', { 
    cwd: repoPath, 
    nodir: true,
    ignore: [
      '**/node_modules/**',
      '**/dist/**',
      '**/build/**',
      '**/coverage/**',
      '**/*.min.js',
      '**/*.bundle.js'
    ]
  });
  
  const result: StaticAnalysisResult = {
    maliciousPatterns: [],
    sensitiveDataAccess: [],
    destructiveBehavior: [],
    networkSuspicious: []
  };

  const excludeRuleFiles = (file: string): boolean => {
    return file.endsWith('detectionPatterns.ts') || 
           file.endsWith('rules.ts') || 
           file.endsWith('patterns.ts') ||
           file.endsWith('detectionPatterns.js') ||
           file.endsWith('rules.js') ||
           file.endsWith('patterns.js');
  };

  for (const file of files) {
    if (checkSafePath(file)) continue;
    if (excludeRuleFiles(file)) continue;
    
    const filePath = path.join(repoPath, file);
    
    if (!fs.existsSync(filePath)) continue;
    
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n');

    lines.forEach((line, index) => {
      if (line.trim().startsWith('//') || line.trim().startsWith('#')) return;
      
      for (const rule of detectionRules) {
        if (shouldExclude(line, rule)) continue;
        
        if (rule.pattern.test(line)) {
          const match: PatternMatch = {
            file,
            line: index + 1,
            code: line.trim().substring(0, 100),
            description: rule.name,
            severity: rule.severity,
            confidence: rule.confidence
          };

          switch (rule.category) {
            case 'malicious':
              result.maliciousPatterns.push(match);
              break;
            case 'sensitive':
              result.sensitiveDataAccess.push(match);
              break;
            case 'destructive':
              result.destructiveBehavior.push(match);
              break;
            case 'network':
              result.networkSuspicious.push(match);
              break;
          }
        }
      }
    });
  }

  return result;
}
