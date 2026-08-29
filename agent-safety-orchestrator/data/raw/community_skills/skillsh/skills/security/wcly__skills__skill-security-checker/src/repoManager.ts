import simpleGit from 'simple-git';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';
import { ParsedSource } from './inputParser';

const TEMP_DIR = '/tmp/skill-security-checker';

export async function cloneRepo(source: ParsedSource): Promise<string> {
  if (!fs.existsSync(TEMP_DIR)) {
    fs.mkdirSync(TEMP_DIR, { recursive: true });
  }

  const timestamp = Date.now();
  let targetDir: string;

  switch (source.type) {
    case 'github':
      targetDir = path.join(TEMP_DIR, `repo-${timestamp}`);
      const git = simpleGit();
      await git.clone(source.repoUrl!, targetDir);
      return targetDir;

    case 'local':
      return source.localPath!;

    case 'npm':
      return downloadNpmPackage(source.npmPackage!);
  }
}

export async function downloadNpmPackage(packageName: string): Promise<string> {
  const targetDir = path.join(TEMP_DIR, `npm-${Date.now()}`);
  fs.mkdirSync(targetDir, { recursive: true });
  
  execSync(`npm pack ${packageName}`, { cwd: targetDir, stdio: 'pipe' });
  
  const tarball = fs.readdirSync(targetDir).find(f => f.endsWith('.tgz'));
  if (tarball) {
    execSync(`tar -xzf ${tarball}`, { cwd: targetDir });
  }
  
  return targetDir;
}
