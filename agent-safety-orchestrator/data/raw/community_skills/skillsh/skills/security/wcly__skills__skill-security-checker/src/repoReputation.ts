import { ParsedSource } from './inputParser';
import { RepoReputationResult } from './types';

export async function getRepoReputation(source: ParsedSource): Promise<RepoReputationResult> {
  if (source.type !== 'github') {
    return {
      stars: 0,
      forks: 0,
      createdAt: 'unknown',
      lastUpdated: 'unknown',
      contributors: 0,
      isOfficial: false
    };
  }

  const repoPath = source.repoUrl!.replace('https://github.com/', '');
  const [owner, repo] = repoPath.split('/');

  const response = await fetch(`https://api.github.com/repos/${owner}/${repo}`, {
    headers: { 'User-Agent': 'SkillSecurityChecker' }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch repo info: ${response.statusText}`);
  }

  const data = await response.json();

  return {
    stars: data.stargazers_count || 0,
    forks: data.forks_count || 0,
    createdAt: data.created_at,
    lastUpdated: data.updated_at,
    contributors: data.contributors?.length || 0,
    isOfficial: false
  };
}
