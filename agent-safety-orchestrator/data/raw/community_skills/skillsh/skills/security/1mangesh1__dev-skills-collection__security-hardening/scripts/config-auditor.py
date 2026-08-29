#!/usr/bin/env python3
"""
Configuration Auditor - Audit application security configuration.
Checks for common misconfigurations and security best practice violations.
"""

import json
from typing import Dict, List
import os
import re

class ConfigurationAuditor:
    """Audit security configuration."""
    
    def __init__(self):
        self.findings = []
        self.severity_levels = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    
    def check_debug_mode(self, configs: Dict) -> List[Dict]:
        """Check if debug mode is enabled in production."""
        findings = []
        
        debug_keys = ['debug', 'debug_mode', 'development_mode', 'dev_mode']
        
        for key, value in configs.items():
            if key.lower() in debug_keys:
                if value in [True, 'true', 'True', 'yes']:
                    findings.append({
                        'type': 'DEBUG_MODE_ENABLED',
                        'severity': 'HIGH',
                        'message': f'Debug mode is enabled: {key}={value}',
                        'recommendation': 'Set debug mode to false in production'
                    })
        
        return findings
    
    def check_default_credentials(self, configs: Dict) -> List[Dict]:
        """Check for default credentials."""
        findings = []
        
        default_passwords = ['password', 'admin', 'root', '12345', 'admin123', 'changeme']
        sensitive_keys = ['password', 'secret', 'api_key', 'token', 'db_password']
        
        for key, value in configs.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if isinstance(value, str):
                    if value.lower() in default_passwords or len(value) < 8:
                        findings.append({
                            'type': 'WEAK_CREDENTIALS',
                            'severity': 'CRITICAL',
                            'message': f'Weak or default credentials for {key}',
                            'recommendation': 'Use strong, unique passwords (12+ characters, mixed case, symbols)'
                        })
        
        return findings
    
    def check_tls_version(self, config: Dict) -> List[Dict]:
        """Check TLS version configuration."""
        findings = []
        
        tls_version = config.get('tls_version') or config.get('ssl_version')
        
        weak_versions = ['ssl', 'tlsv1', 'tlsv1.0', 'tlsv1.1']
        
        if tls_version and isinstance(tls_version, str):
            if tls_version.lower() in weak_versions:
                findings.append({
                    'type': 'WEAK_TLS_VERSION',
                    'severity': 'HIGH',
                    'message': f'Using weak TLS version: {tls_version}',
                    'recommendation': 'Use TLS 1.2 or higher (preferably 1.3)'
                })
        
        return findings
    
    def check_cors_config(self, config: Dict) -> List[Dict]:
        """Check CORS configuration."""
        findings = []
        
        allowed_origins = config.get('cors_allowed_origins', config.get('allowed_origins', []))
        
        if '*' in allowed_origins or (isinstance(allowed_origins, str) and allowed_origins == '*'):
            findings.append({
                'type': 'OVERLY_PERMISSIVE_CORS',
                'severity': 'HIGH',
                'message': 'CORS allows all origins (*)',
                'recommendation': 'Specify explicit allowed origins instead of using wildcard'
            })
        
        return findings
    
    def check_authentication(self, config: Dict) -> List[Dict]:
        """Check authentication configuration."""
        findings = []
        
        # Check for auth enabled
        if config.get('authentication_enabled') in [False, 'false', 'no']:
            findings.append({
                'type': 'AUTHENTICATION_DISABLED',
                'severity': 'CRITICAL',
                'message': 'Authentication is disabled',
                'recommendation': 'Enable authentication for all endpoints'
            })
        
        # Check for JWT expiration
        jwt_expiry = config.get('jwt_expiration_minutes', config.get('token_expiry_minutes'))
        if jwt_expiry and jwt_expiry > 86400:  # > 1 day
            findings.append({
                'type': 'LONG_JWT_EXPIRY',
                'severity': 'MEDIUM',
                'message': f'JWT expiration is {jwt_expiry} minutes (too long)',
                'recommendation': 'Set JWT expiration to 1 hour or less'
            })
        
        return findings
    
    def check_database_config(self, config: Dict) -> List[Dict]:
        """Check database configuration."""
        findings = []
        
        db_config = config.get('database', {})
        
        # Check for SSL
        if not db_config.get('ssl_enabled'):
            findings.append({
                'type': 'DATABASE_SSL_DISABLED',
                'severity': 'HIGH',
                'message': 'Database connections do not use SSL',
                'recommendation': 'Enable SSL for all database connections'
            })
        
        # Check query escaping
        if db_config.get('prepared_statements_enabled') in [False, 'false']:
            findings.append({
                'type': 'SQL_INJECTION_RISK',
                'severity': 'CRITICAL',
                'message': 'Prepared statements are not enabled',
                'recommendation': 'Always use parameterized queries/prepared statements'
            })
        
        return findings
    
    def check_logging_config(self, config: Dict) -> List[Dict]:
        """Check logging configuration."""
        findings = []
        
        log_level = config.get('log_level', '').upper()
        
        if log_level in ['DEBUG', 'TRACE']:
            findings.append({
                'type': 'OVERLY_VERBOSE_LOGGING',
                'severity': 'MEDIUM',
                'message': f'Log level is set to {log_level}',
                'recommendation': 'Use INFO level in production to avoid logging sensitive data'
            })
        
        # Check for secret logging
        if config.get('log_secrets') in [True, 'true']:
            findings.append({
                'type': 'SECRETS_IN_LOGS',
                'severity': 'CRITICAL',
                'message': 'Configuration will log secrets',
                'recommendation': 'Never log passwords, tokens, or other secrets'
            })
        
        return findings
    
    def audit_config_file(self, filepath: str) -> Dict:
        """Audit a configuration file."""
        try:
            with open(filepath, 'r') as f:
                if filepath.endswith('.json'):
                    config = json.load(f)
                else:
                    # Simple key=value parsing
                    config = {}
                    for line in f:
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip()
            
            all_findings = []
            all_findings.extend(self.check_debug_mode(config))
            all_findings.extend(self.check_default_credentials(config))
            all_findings.extend(self.check_tls_version(config))
            all_findings.extend(self.check_cors_config(config))
            all_findings.extend(self.check_authentication(config))
            all_findings.extend(self.check_database_config(config))
            all_findings.extend(self.check_logging_config(config))
            
            return {
                'file': filepath,
                'findings_count': len(all_findings),
                'critical_count': len([f for f in all_findings if f['severity'] == 'CRITICAL']),
                'findings': all_findings
            }
        
        except Exception as e:
            return {
                'file': filepath,
                'error': str(e)
            }

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: config-auditor.py <config_file>")
        sys.exit(1)
    
    auditor = ConfigurationAuditor()
    report = auditor.audit_config_file(sys.argv[1])
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
