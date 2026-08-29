import { InputSource } from './types';

export interface ParsedSource {
  type: 'github' | 'local' | 'npm';
  repoUrl?: string;
  localPath?: string;
  npmPackage?: string;
}

export function parseInput(source: InputSource): ParsedSource {
  switch (source.type) {
    case 'github':
      return {
        type: 'github',
        repoUrl: source.path
      };
    case 'local':
      return {
        type: 'local',
        localPath: source.path
      };
    case 'npm':
      return {
        type: 'npm',
        npmPackage: source.path
      };
  }
}
