import * as fs from 'fs';
import * as path from 'path';

export interface RuntimeBehavior {
  dangerousScripts: string[];
  suspiciousFileAccess: string[];
  networkConnections: string[];
}

export async function monitorRuntime(repoPath: string): Promise<RuntimeBehavior> {
  const behavior: RuntimeBehavior = {
    dangerousScripts: [],
    suspiciousFileAccess: [],
    networkConnections: []
  };

  const pkgJsonPath = path.join(repoPath, 'package.json');
  if (fs.existsSync(pkgJsonPath)) {
    try {
      const pkg = JSON.parse(fs.readFileSync(pkgJsonPath, 'utf-8'));
      
      const dangerousScripts = ['preinstall', 'postinstall', 'prepublish', 'prepare', 'prepack'];
      for (const script of dangerousScripts) {
        if (pkg.scripts && pkg.scripts[script]) {
          const scriptContent = pkg.scripts[script];
          behavior.dangerousScripts.push(`${script}: ${scriptContent}`);
          
          if (containsSuspiciousPatterns(scriptContent)) {
            behavior.suspiciousFileAccess.push(`Suspicious ${script} script detected`);
          }
        }
      }

      if (pkg.dependencies) {
        for (const dep of Object.keys(pkg.dependencies)) {
          if (isSuspiciousPackage(dep)) {
            behavior.networkConnections.push(`Suspicious dependency: ${dep}`);
          }
        }
      }
    } catch (e) {
      // ignore parse errors
    }
  }

  return behavior;
}

function containsSuspiciousPatterns(script: string): boolean {
  const suspiciousPatterns = [
    /curl.*\|.*sh/i,
    /wget.*\|.*sh/i,
    /eval\s*\(/i,
    /child_process/i,
    /exec\s*\(/i,
    /\$.*\$\(/i,
    /base64/i,
    /decodeURIComponent/i,
    /\.env/i,
    /process\.cwd/i,
    /fs\.(readFile|writeFile|unlink)/i
  ];

  return suspiciousPatterns.some(pattern => pattern.test(script));
}

function isSuspiciousPackage(pkg: string): boolean {
  const suspiciousPackages = [
    'hidden',
    'stealer',
    'miner',
    'cryptominer',
    'backdoor',
    'rootkit',
    'keylogger'
  ];

  return suspiciousPackages.some(suspicious => pkg.toLowerCase().includes(suspicious));
}
