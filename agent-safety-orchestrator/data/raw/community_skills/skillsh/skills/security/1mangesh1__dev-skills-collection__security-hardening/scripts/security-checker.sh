#!/bin/bash
# Security Hardening Checker - Validate security best practices
# Performs comprehensive security checks on infrastructure

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_firewall() {
    echo "Checking firewall rules..."
    
    if command -v ufw &> /dev/null; then
        ufw status numbered
    elif command -v firewall-cmd &> /dev/null; then
        firewall-cmd --list-all
    else
        echo -e "${YELLOW}Warning: No firewall management tool found${NC}"
    fi
}

check_ssh_config() {
    echo "Checking SSH configuration..."
    
    local ssh_config="/etc/ssh/sshd_config"
    local issues=0
    
    # Check if PermitRootLogin is disabled
    if ! grep -q "^PermitRootLogin no" "$ssh_config" 2>/dev/null; then
        echo -e "${RED}✗ Root login should be disabled${NC}"
        ((issues++))
    else
        echo -e "${GREEN}✓ Root login disabled${NC}"
    fi
    
    # Check password authentication
    if ! grep -q "^PasswordAuthentication no" "$ssh_config" 2>/dev/null; then
        echo -e "${YELLOW}⚠ Consider disabling password authentication${NC}"
    else
        echo -e "${GREEN}✓ Password authentication disabled${NC}"
    fi
    
    # Check for key-based authentication
    if grep -q "^PubkeyAuthentication yes" "$ssh_config" 2>/dev/null; then
        echo -e "${GREEN}✓ Public key authentication enabled${NC}"
    else
        echo -e "${YELLOW}⚠ Enable public key authentication${NC}"
    fi
    
    return $issues
}

check_file_permissions() {
    echo "Checking critical file permissions..."
    
    local issues=0
    
    # Check /etc/passwd
    local perms=$(stat -f %OLp /etc/passwd 2>/dev/null || stat -c %a /etc/passwd 2>/dev/null || echo "unknown")
    if [[ "$perms" != "644" ]]; then
        echo -e "${YELLOW}⚠ /etc/passwd should have 644 permissions (current: $perms)${NC}"
        ((issues++))
    else
        echo -e "${GREEN}✓ /etc/passwd has correct permissions${NC}"
    fi
    
    # Check /etc/shadow
    if [[ -f /etc/shadow ]]; then
        perms=$(stat -f %OLp /etc/shadow 2>/dev/null || stat -c %a /etc/shadow 2>/dev/null || echo "unknown")
        if [[ "$perms" != "000" ]] && [[ "$perms" != "640" ]]; then
            echo -e "${YELLOW}⚠ /etc/shadow should have restrictive permissions (current: $perms)${NC}"
            ((issues++))
        else
            echo -e "${GREEN}✓ /etc/shadow has secure permissions${NC}"
        fi
    fi
    
    return $issues
}

check_selinux_apparmor() {
    echo "Checking SELinux/AppArmor status..."
    
    if command -v getenforce &> /dev/null; then
        status=$(getenforce)
        if [[ "$status" == "Enforcing" ]] || [[ "$status" == "Permissive" ]]; then
            echo -e "${GREEN}✓ SELinux is active: $status${NC}"
        else
            echo -e "${YELLOW}⚠ SELinux is disabled${NC}"
        fi
    elif command -v aa-status &> /dev/null; then
        echo -e "${GREEN}✓ AppArmor is installed${NC}"
    else
        echo -e "${YELLOW}⚠ Neither SELinux nor AppArmor found${NC}"
    fi
}

check_sudo_config() {
    echo "Checking sudo configuration..."
    
    # Check for NOPASSWD
    if grep -r "NOPASSWD" /etc/sudoers* 2>/dev/null; then
        echo -e "${RED}✗ NOPASSWD entries found in sudoers${NC}"
    else
        echo -e "${GREEN}✓ No NOPASSWD entries found${NC}"
    fi
    
    # Check for secure path
    if grep "^Defaults.*secure_path" /etc/sudoers 2>/dev/null; then
        echo -e "${GREEN}✓ secure_path is configured${NC}"
    else
        echo -e "${YELLOW}⚠ Consider configuring secure_path in sudoers${NC}"
    fi
}

check_package_updates() {
    echo "Checking for security updates..."
    
    if command -v apt &> /dev/null; then
        updates=$(apt list --upgradable 2>/dev/null | grep -c "upgradable" || echo 0)
        if [[ $updates -gt 0 ]]; then
            echo -e "${YELLOW}⚠ $updates security updates available${NC}"
        else
            echo -e "${GREEN}✓ System is up to date${NC}"
        fi
    elif command -v yum &> /dev/null; then
        updates=$(yum check-update 2>/dev/null | grep -c "^" || echo 0)
        echo -e "${YELLOW}⚠ Check for updates with 'sudo yum check-update'${NC}"
    fi
}

check_password_policy() {
    echo "Checking password policy..."
    
    if [[ -f /etc/pam.d/common-password ]]; then
        if grep -q "pam_pwquality" /etc/pam.d/common-password 2>/dev/null; then
            echo -e "${GREEN}✓ Password quality enforcement enabled${NC}"
        else
            echo -e "${YELLOW}⚠ Consider enabling password quality enforcement${NC}"
        fi
    fi
}

check_audit_logging() {
    echo "Checking audit logging..."
    
    if command -v auditctl &> /dev/null; then
        if auditctl -l | grep -q rule 2>/dev/null; then
            echo -e "${GREEN}✓ Audit logging is configured${NC}"
        else
            echo -e "${YELLOW}⚠ Audit rules not configured${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Audit daemon (auditd) not installed${NC}"
    fi
}

generate_report() {
    echo ""
    echo "========================================"
    echo "Security Hardening Report"
    echo "========================================"
    echo ""
    
    check_firewall
    echo ""
    check_ssh_config
    echo ""
    check_file_permissions
    echo ""
    check_selinux_apparmor
    echo ""
    check_sudo_config
    echo ""
    check_package_updates
    echo ""
    check_password_policy
    echo ""
    check_audit_logging
}

main() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${YELLOW}Warning: Some checks require root privileges. Run with sudo for complete report.${NC}"
    fi
    
    generate_report
}

main "$@"
