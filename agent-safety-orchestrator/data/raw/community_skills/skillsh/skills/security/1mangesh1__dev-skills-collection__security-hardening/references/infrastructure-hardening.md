# Infrastructure Security Hardening

## Network Security

### Firewall Configuration

**UFW (Uncomplicated Firewall) Example:**
```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Block everything by default
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable

# Rate limiting on SSH
sudo ufw limit 22/tcp
```

### Network Segmentation

```
Internet → Load Balancer
          ↓
        DMZ (Web Layer)
          ↓
Internal Network (App Layer)
          ↓
Database Layer (Isolated)
```

**Benefits:**
- Compromised web server can't directly access database
- Lateral movement restricted
- Better visibility and monitoring

### VPC and Security Groups (AWS)

```yaml
SecurityGroup:
  ingress:
    - protocol: tcp
      port_range: 443
      source: 0.0.0.0/0  # HTTPS from anywhere
    
    - protocol: tcp
      port_range: 22
      source: 203.0.113.0/24  # SSH from office only
  
  egress:
    - protocol: tcp
      port_range: 443
      destination: 0.0.0.0/0  # HTTPS to anywhere
```

## Operating System Hardening

### 1. User and Privilege Management

```bash
# Delete default accounts
sudo userdel ubuntu
sudo userdel -r hadoop

# Restrict sudo access
visudo  # Add specific users to sudoers group

# Use strong password policy
# Configure PAM in /etc/pam.d/common-password
```

### 2. SSH Hardening

**Configure /etc/ssh/sshd_config:**
```
# Disable root login
PermitRootLogin no

# Use key-based authentication only
PubkeyAuthentication yes
PasswordAuthentication no

# Change default port
Port 2222

# Limit login attempts
MaxAuthTries 3

# Disable X11 forwarding
X11Forwarding no

# Only allow specific users
AllowUsers deploy monitoring

# Set idle timeout
ClientAliveInterval 300
ClientAliveCountMax 0

# Disable empty passwords
PermitEmptyPasswords no

# Use strong ciphers
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com

# Protocol version 2 only
Protocol 2
```

### 3. File System Permissions

```bash
# Secure permissions checklist
chmod 644 /etc/passwd
chmod 000 /etc/shadow
chmod 644 /etc/group
chmod 000 /etc/gshadow

# World-writable directories
chmod 1777 /tmp /var/tmp

# Remove SUID bits on unnecessary binaries
find / -perm -4000 -type f -exec ls -la {} \;
```

### 4. SELinux / AppArmor

**SELinux:**
```bash
# Check status
getenforce

# Set to enforcing (after testing)
sudo setenforce 1

# View policies
semanage fcontext -l
```

**AppArmor (Ubuntu/Debian):**
```bash
# Enable profile
sudo aa-enforce /etc/apparmor.d/usr.bin.man

# Create custom policy
sudo aa-logprof
```

## Service Hardening

### Run Services with Minimal Privileges

```bash
# Create dedicated user for service
useradd -r -s /bin/false myservice

# Run service as that user
sudo -u myservice /path/to/service
```

### Disable Unnecessary Services

```bash
# Ubuntu/Debian
systemctl list-unit-files | grep enabled
systemctl disable telnet
systemctl disable ftp

# Remove unnecessary packages
apt-get remove --purge telnet ftp
```

### Container Security (Docker)

```dockerfile
# Run as non-root
RUN useradd -r appuser
USER appuser

# Minimize base image
FROM debian:bookworm-slim

# Read-only root filesystem
RUN mount -o remount,ro /

# Drop unnecessary capabilities
RUN setcap -r /usr/bin/ping

# Set resource limits
# Use:
# docker run --memory="256m" --cpus="0.5"
```

## Log Management and Auditing

### Centralized Logging

```conf
# Send logs to central server
*.* @@logserver.example.com:514

# Don't log locally after forwarding
:omprog: ^stop
```

### Audit Logging

```bash
# Install auditd
sudo apt-get install auditd

# Configure audit rules
cat /etc/audit/rules.d/audit.rules:
  -w /etc/passwd -p wa -k passwd_changes
  -w /etc/shadow -p wa -k password_changes
  -a always,exit -F arch=b64 -S adopen,openat -F auid>=1000 -F auid!=4294967295 -k file_access

# View logs
sudo ausearch -k passwd_changes
```

## Update Management

### Regular Patching Strategy

```bash
# Weekly security updates
sudo apt-get update
sudo apt-get upgrade -y

# Enable automatic security updates
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

## Security Scanning

### Vulnerability Scanning

```bash
# OS-level scanning
apt-get install lynis
sudo lynis audit system

# Container scanning
trivy image myimage:latest

# Dependency scanning
npm audit
pip-audit
```

### Penetration Testing

```
- Port scanning: nmap
- Web vulnerability: OWASP ZAP, Burp Suite
- Configuration scanning: lynis, CIS-CAT
- Network testing: Nessus, OpenVAS
```
