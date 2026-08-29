#!/usr/bin/env node

/**
 * Secure Vault - Encrypted secrets storage
 * Inspired by ZeroClaw's encrypted secrets with XOR + local key file
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { fileURLToPath } from 'url';
import os from 'os';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const VAULT_DIR = process.env.VAULT_DIR || path.join(os.homedir(), '.config', 'agent');
const KEY_FILE = path.join(VAULT_DIR, 'vault.key');
const VAULT_FILE = path.join(VAULT_DIR, 'vault.enc');

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function getOrCreateKey(externalKey) {
  if (externalKey) {
    return Buffer.from(externalKey, 'hex');
  }
  
  ensureDir(VAULT_DIR);
  
  if (fs.existsSync(KEY_FILE)) {
    return fs.readFileSync(KEY_FILE);
  }
  
  // Generate new key
  const key = crypto.randomBytes(32);
  fs.writeFileSync(KEY_FILE, key, { mode: 0o600 });
  return key;
}

function encrypt(plaintext, key) {
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
  
  let encrypted = cipher.update(plaintext, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  
  const authTag = cipher.getAuthTag();
  
  return {
    iv: iv.toString('hex'),
    data: encrypted,
    tag: authTag.toString('hex')
  };
}

function decrypt(encryptedObj, key) {
  const iv = Buffer.from(encryptedObj.iv, 'hex');
  const authTag = Buffer.from(encryptedObj.tag, 'hex');
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
  
  decipher.setAuthTag(authTag);
  
  let decrypted = decipher.update(encryptedObj.data, 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  
  return decrypted;
}

function loadVault(key) {
  ensureDir(VAULT_DIR);
  
  if (!fs.existsSync(VAULT_FILE)) {
    return {};
  }
  
  try {
    const encrypted = JSON.parse(fs.readFileSync(VAULT_FILE, 'utf-8'));
    const decrypted = decrypt(encrypted, key);
    return JSON.parse(decrypted);
  } catch (e) {
    // Vault corrupted or wrong key
    return {};
  }
}

function saveVault(vault, key) {
  ensureDir(VAULT_DIR);
  
  const plaintext = JSON.stringify(vault);
  const encrypted = encrypt(plaintext, key);
  
  fs.writeFileSync(VAULT_FILE, JSON.stringify(encrypted), { mode: 0o600 });
}

async function cmdSet(options) {
  const { name, value, key } = options;
  
  if (!name) {
    throw new Error('--name is required');
  }
  if (!value) {
    throw new Error('--value is required');
  }
  
  const encryptionKey = getOrCreateKey(key);
  const vault = loadVault(encryptionKey);
  
  vault[name] = value;
  saveVault(vault, encryptionKey);
  
  return { success: true, name, encrypted: true };
}

async function cmdGet(options) {
  const { name, key } = options;
  
  if (!name) {
    throw new Error('--name is required');
  }
  
  const encryptionKey = getOrCreateKey(key);
  const vault = loadVault(encryptionKey);
  
  if (!(name in vault)) {
    return { found: false, name };
  }
  
  return { found: true, name, value: vault[name] };
}

async function cmdList(options) {
  const { key } = options;
  
  const encryptionKey = getOrCreateKey(key);
  const vault = loadVault(encryptionKey);
  
  return { secrets: Object.keys(vault), count: Object.keys(vault).length };
}

async function cmdDelete(options) {
  const { name, key } = options;
  
  if (!name) {
    throw new Error('--name is required');
  }
  
  const encryptionKey = getOrCreateKey(key);
  const vault = loadVault(encryptionKey);
  
  if (!(name in vault)) {
    return { success: false, name, message: 'Secret not found' };
  }
  
  // Secure delete - overwrite before removing
  vault[name] = '';
  delete vault[name];
  saveVault(vault, encryptionKey);
  
  return { success: true, name };
}

async function cmdExport(options) {
  const { output, key } = options;
  
  if (!output) {
    throw new Error('--output is required');
  }
  
  ensureDir(VAULT_DIR);
  
  if (!fs.existsSync(KEY_FILE) && !key) {
    throw new Error('No vault key found. Cannot export without existing vault or --key');
  }
  
  const encryptionKey = getOrCreateKey(key);
  
  // Export both encrypted vault and key proof
  const vault = loadVault(encryptionKey);
  const exportData = {
    version: 1,
    exportedAt: new Date().toISOString(),
    vault: vault,
    // Add a verification hash
    verification: crypto.createHash('sha256').update(JSON.stringify(vault)).digest('hex').slice(0, 16)
  };
  
  const exportKey = crypto.randomBytes(32);
  const encrypted = encrypt(JSON.stringify(exportData), exportKey);
  
  // Export the key with the provided external key or as a separate file
  if (key) {
    const encryptedExportKey = encrypt(exportKey.toString('hex'), Buffer.from(key, 'hex'));
    fs.writeFileSync(output, JSON.stringify({
      data: encrypted,
      key: encryptedExportKey
    }), { mode: 0o600 });
  } else {
    // Export key separately (less secure but more portable)
    fs.writeFileSync(output, JSON.stringify({
      data: encrypted,
      key: exportKey.toString('hex')
    }), { mode: 0o600 });
  }
  
  return { success: true, output, secrets: Object.keys(vault).length };
}

async function cmdImport(options) {
  const { path: filePath, key: externalKey } = options;
  
  if (!filePath) {
    throw new Error('--path is required');
  }
  
  if (!fs.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }
  
  const content = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  
  let exportKey;
  if (externalKey) {
    const encryptedKey = JSON.parse(content.key);
    exportKey = Buffer.from(decrypt(encryptedKey, Buffer.from(externalKey, 'hex')), 'hex');
  } else {
    exportKey = Buffer.from(content.key, 'hex');
  }
  
  const decrypted = decrypt(content.data, exportKey);
  const importData = JSON.parse(decrypted);
  
  const encryptionKey = getOrCreateKey(externalKey);
  const vault = loadVault(encryptionKey);
  
  // Merge vaults (imported secrets take precedence)
  Object.assign(vault, importData.vault);
  saveVault(vault, encryptionKey);
  
  return { success: true, imported: Object.keys(importData.vault).length };
}

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  
  try {
    if (command === 'set') {
      const options = {
        name: getArgValue(args, '--name'),
        value: getArgValue(args, '--value'),
        key: getArgValue(args, '--key')
      };
      
      if (!options.name || !options.value) {
        console.error('Error: --name and --value are required');
        process.exit(1);
      }
      
      const result = await cmdSet(options);
      console.log(JSON.stringify(result, null, 2));
      
    } else if (command === 'get') {
      const options = {
        name: getArgValue(args, '--name'),
        key: getArgValue(args, '--key')
      };
      
      if (!options.name) {
        console.error('Error: --name is required');
        process.exit(1);
      }
      
      const result = await cmdGet(options);
      console.log(JSON.stringify(result, null, 2));
      
    } else if (command === 'list') {
      const options = {
        key: getArgValue(args, '--key')
      };
      
      const result = await cmdList(options);
      console.log(JSON.stringify(result, null, 2));
      
    } else if (command === 'delete' || command === 'del') {
      const options = {
        name: getArgValue(args, '--name'),
        key: getArgValue(args, '--key')
      };
      
      if (!options.name) {
        console.error('Error: --name is required');
        process.exit(1);
      }
      
      const result = await cmdDelete(options);
      console.log(JSON.stringify(result, null, 2));
      
    } else if (command === 'export') {
      const options = {
        output: getArgValue(args, '--output'),
        key: getArgValue(args, '--key')
      };
      
      if (!options.output) {
        console.error('Error: --output is required');
        process.exit(1);
      }
      
      const result = await cmdExport(options);
      console.log(JSON.stringify(result, null, 2));
      
    } else if (command === 'import') {
      const options = {
        path: getArgValue(args, '--path'),
        key: getArgValue(args, '--key')
      };
      
      if (!options.path) {
        console.error('Error: --path is required');
        process.exit(1);
      }
      
      const result = await cmdImport(options);
      console.log(JSON.stringify(result, null, 2));
      
    } else {
      console.log(`
Secure Vault - Encrypted secrets storage

Usage:
  secure-vault.js set --name <name> --value <value> [options]
  secure-vault.js get --name <name> [options]
  secure-vault.js list [options]
  secure-vault.js delete --name <name> [options]
  secure-vault.js export --output <path> [options]
  secure-vault.js import --path <path> [options]

Commands:
  set     Store a secret
  get     Retrieve a secret
  list    List all secret names
  delete  Delete a secret
  export  Export vault (encrypted)
  import  Import vault

Examples:
  secure-vault.js set --name api_key --value "sk-xxx"
  secure-vault.js get --name api_key
  secure-vault.js list
  secure-vault.js delete --name api_key
  secure-vault.js export --output backup.enc
  secure-vault.js import --path backup.enc
`);
      process.exit(1);
    }
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

function getArgValue(args, flag) {
  const index = args.indexOf(flag);
  if (index === -1 || index + 1 >= args.length) return null;
  return args[index + 1];
}

main();
