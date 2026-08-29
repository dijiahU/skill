import { SecurityCheckResult, OutputFormat } from './types';

export function generateReport(result: SecurityCheckResult, format: OutputFormat): string {
  switch (format) {
    case 'json':
      return JSON.stringify(result, null, 2);

    case 'friendly':
      return generateFriendlyReport(result);

    case 'concise':
      return generateConciseReport(result);

    default:
      return generateConciseReport(result);
  }
}

function generateFriendlyReport(result: SecurityCheckResult): string {
  const riskEmoji = result.riskLevel === 'high' ? '🔴' : 
                    result.riskLevel === 'medium' ? '⚠️' : '✅';
  const recEmoji = result.recommendation === 'download' ? '✅' : '❌';

  let report = `
╔══════════════════════════════════════════════════════╗
║              Skill 安全检查报告                      ║
╠══════════════════════════════════════════════════════╣
  ${riskEmoji} 风险等级: ${result.riskLevel.toUpperCase()}
  📊 安全评分: ${result.score}/100
  ${recEmoji} 推荐: ${result.recommendation === 'download' ? '可下载' : '不建议下载'}
╠══════════════════════════════════════════════════════╣
`;

  if (result.reasons.length > 0) {
    report += `⚠️ 风险原因:\n`;
    for (const reason of result.reasons) {
      report += `   - ${reason}\n`;
    }
  }

  report += `📈 仓库信息:\n`;
  report += `   ⭐ Stars: ${result.details.stars}\n`;
  report += `   🍴 Forks: ${result.details.forks}\n`;
  report += `   👥 贡献者: ${result.details.contributors}\n`;

  report += `╚══════════════════════════════════════════════════════╝`;

  return report;
}

function generateConciseReport(result: SecurityCheckResult): string {
  const status = result.recommendation === 'download' ? '可下载' : '不建议下载';
  let report = `[${status}] 安全评分: ${result.score}/100 (${result.riskLevel}风险)\n`;

  if (result.reasons.length > 0) {
    report += `原因: ${result.reasons.join('; ')}`;
  }

  return report;
}
