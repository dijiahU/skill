import { PatternMatch } from './types';

export interface DetectionRule {
  name: string;
  pattern: RegExp;
  excludePatterns?: RegExp[];
  description: string;
  severity: 'high' | 'medium' | 'low';
  category: 'malicious' | 'sensitive' | 'destructive' | 'network';
  confidence: 'high' | 'medium' | 'low';
}

const safePatterns = [
  /node_modules/,
  /\.git\//,
  /dist\//,
  /build\//,
  /coverage\//,
  /\.test\.([jt]s)$/,
  /\.spec\.([jt]s)$/,
  /__tests__\//,
  /mock[s]?\//,
  /fixture[s]?\//,
  /example[s]?\//,
  /sample[s]?\//,
  /test-*/,
];

const safeCodePatterns = [
  /console\.log.*process\.env/i,
  /if.*process\.env.*===/i,
  /process\.env.*\?/i,
  /const.*=.*process\.env.*\|\|.*/i,
  /tsconfig/,
  /jest\.config/,
  /webpack/,
  /\.env\./,
  /\.env$/,
  /eslint/,
  /prettier/,
  /vitest/,
  /mocha/,
  /cypress/,
  /playwright/,
  /debug/,
  /logger/,
  /log4j/,
  /winston/,
  /bunyan/,
  /pino/,
  /sentry/,
  /datadog/,
  /newrelic/,
];

function isSafePath(filePath: string): boolean {
  return safePatterns.some(pattern => pattern.test(filePath));
}

function isSafeCode(line: string, filePath: string): boolean {
  if (isSafePath(filePath)) return true;
  return safeCodePatterns.some(pattern => {
    const match = pattern.test(line);
    if (match) return true;
    if (pattern.test(filePath)) return true;
    return false;
  });
}

export function checkSafePath(filePath: string): boolean {
  return isSafePath(filePath);
}

export function checkSafeCode(line: string, filePath: string): boolean {
  return isSafeCode(line, filePath);
}

export const detectionRules: DetectionRule[] = [
  {
    name: 'base64 encoded payload',
    pattern: /eval\s*\(\s*atob\s*\(\s*['"`][A-Za-z0-9+/=]{20,}['"`]\s*\)/i,
    excludePatterns: [
      /test/i,
      /mock/i,
      /example/i,
      /demo/i,
    ],
    description: '检测到 base64 解码后执行代码',
    severity: 'high',
    category: 'malicious',
    confidence: 'high'
  },
  {
    name: 'command injection',
    pattern: /(eval|exec|spawn|execSync)\s*\(\s*.*\$\(/i,
    excludePatterns: [
      /test/i,
      /mock/i,
    ],
    description: '检测到命令注入风险',
    severity: 'high',
    category: 'malicious',
    confidence: 'medium'
  },
  {
    name: 'dynamic code execution with user input',
    pattern: /(eval|Function|new\s+Function)\s*\(\s*.*(\+|concat|template)/i,
    excludePatterns: [
      /test/i,
      /mock/i,
      /example/i,
      /test-utils/i,
    ],
    description: '检测到动态代码执行',
    severity: 'high',
    category: 'malicious',
    confidence: 'medium'
  },
  {
    name: 'obfuscated string decode',
    pattern: /\.fromCharCode\s*\(\s*\d+\s*\)\s*(\.fromCharCode\s*\()/i,
    description: '检测到字符串混淆解码',
    severity: 'medium',
    category: 'malicious',
    confidence: 'low'
  },
  {
    name: 'read SSH private key',
    pattern: /fs\.readFileSync\s*\(\s*.*(\.ssh\/id_(?:rsa|ed25519|dsa))/i,
    description: '检测到读取 SSH 私钥',
    severity: 'high',
    category: 'sensitive',
    confidence: 'high'
  },
  {
    name: 'access credential files',
    pattern: /fs\.readFileSync\s*\(\s*.*\.(pem|key|crt|p12|keystore)/i,
    description: '检测到访问证书文件',
    severity: 'high',
    category: 'sensitive',
    confidence: 'medium'
  },
  {
    name: 'access token files',
    pattern: /fs\.readFileSync\s*\(\s*.*\.(npmrc|netrc|git-credentials)/i,
    description: '检测到访问凭证文件',
    severity: 'high',
    category: 'sensitive',
    confidence: 'high'
  },
  {
    name: 'read environment variables for secrets',
    pattern: /process\.env\.[A-Z_]*(?:TOKEN|SECRET|KEY|PASSWORD|PRIVATE)/i,
    excludePatterns: [
      /console\.log/i,
      /logger/i,
      /debug/i,
      /TEST/i,
      /MOCK/i,
      /example/i,
    ],
    description: '检测到读取可能包含密钥的环境变量',
    severity: 'medium',
    category: 'sensitive',
    confidence: 'medium'
  },
  {
    name: 'send credentials in request',
    pattern: /(fetch|axios|http\.request)\s*\(.*(headers|body).*(token|password|secret|key).*(?!safe|public)/i,
    excludePatterns: [
      /test/i,
      /mock/i,
      /example/i,
    ],
    description: '检测到请求中可能包含敏感数据',
    severity: 'high',
    category: 'sensitive',
    confidence: 'medium'
  },
  {
    name: 'dangerous file deletion',
    pattern: /(rmSync|rmdirSync|unlinkSync)\s*\(\s*['"`]\/(?:etc|usr|bin|var|home|root)/i,
    description: '检测到危险路径文件删除',
    severity: 'high',
    category: 'destructive',
    confidence: 'high'
  },
  {
    name: 'recursive force delete',
    pattern: /(rmSync|rm)\s*\(.*['"`]\s*(-rf|-r\s+-f)/i,
    excludePatterns: [
      /test/i,
      /mock/i,
    ],
    description: '检测到递归强制删除',
    severity: 'high',
    category: 'destructive',
    confidence: 'medium'
  },
  {
    name: 'modify system files',
    pattern: /(writeFileSync|appendFileSync)\s*\(\s*['"`]\/(?:etc\/|system32|registry)/i,
    description: '检测到修改系统配置文件',
    severity: 'high',
    category: 'destructive',
    confidence: 'high'
  },
  {
    name: 'reverse shell bash',
    pattern: /(bash|zsh|sh)\s+-[ic]\s*['"`].*(\/dev\/tcp|UDP)/i,
    description: '检测到反弹 shell 特征',
    severity: 'high',
    category: 'network',
    confidence: 'high'
  },
  {
    name: 'netcat reverse shell',
    pattern: /nc\s+-[elvp]\s+\d+/i,
    description: '检测到 netcat 反弹 shell',
    severity: 'high',
    category: 'network',
    confidence: 'high'
  },
  {
    name: 'external data exfiltration',
    pattern: /fetch\s*\(\s*['"`]https?:\/\/[^'"`]+(?:exe|dll|zip|bin)/i,
    description: '检测到可疑外部数据下载',
    severity: 'medium',
    category: 'network',
    confidence: 'medium'
  },
  {
    name: 'suspicious domain communication',
    pattern: /fetch\s*\(\s*['"`]https?:\/\/[a-z0-9]{20,}\./i,
    excludePatterns: [
      /test/i,
      /localhost/i,
      /127\.0\.0\.1/,
    ],
    description: '检测到可疑域名通信',
    severity: 'medium',
    category: 'network',
    confidence: 'low'
  },
  {
    name: 'child_process with shell',
    pattern: /child_process\.(exec|execSync|spawn)\s*\(.*shell:\s*true/i,
    excludePatterns: [
      /test/i,
      /mock/i,
      /example/i,
    ],
    description: '检测到使用 shell 执行子进程',
    severity: 'medium',
    category: 'malicious',
    confidence: 'low'
  },
  {
    name: 'encoded powerShell',
    pattern: /powershell.*-enc|-encodedcommand/i,
    description: '检测到编码 PowerShell 命令',
    severity: 'high',
    category: 'malicious',
    confidence: 'high'
  },
  {
    name: 'download and execute',
    pattern: /(curl|wget|fetch).*\|\s*(bash|sh|powershell)/i,
    description: '检测到下载并执行脚本',
    severity: 'high',
    category: 'malicious',
    confidence: 'high'
  },
  {
    name: 'crypto currency mining',
    pattern: /(stratum\+tcp|coinhive|coin-hive|cryptonight)/i,
    description: '检测到加密货币挖矿特征',
    severity: 'high',
    category: 'malicious',
    confidence: 'high'
  }
];

export function shouldExclude(line: string, rule: DetectionRule): boolean {
  if (!rule.excludePatterns) return false;
  return rule.excludePatterns.some(pattern => pattern.test(line));
}
