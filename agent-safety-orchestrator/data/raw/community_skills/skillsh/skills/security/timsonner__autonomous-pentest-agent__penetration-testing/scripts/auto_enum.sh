#!/bin/bash
# auto_enum.sh - Automated enumeration script for penetration testing
# 
# Usage: ./auto_enum.sh <TARGET_IP>
# 
# This script performs comprehensive automated enumeration including:
# - Port scanning
# - Service detection
# - Web directory enumeration
# - SMB enumeration
# - Basic vulnerability scanning
#
# All output is saved to the enumeration_results/ directory

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if target IP is provided
if [ -z "$1" ]; then
    echo -e "${RED}[!] Usage: $0 <TARGET_IP>${NC}"
    exit 1
fi

TARGET="$1"
OUTPUT_DIR="enumeration_results_${TARGET}"

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║            Automated Enumeration Script                  ║"
echo "║                  Target: $TARGET                          ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Create output directory
echo -e "${GREEN}[+] Creating output directory: $OUTPUT_DIR${NC}"
mkdir -p "$OUTPUT_DIR"

# Function to check if tool is installed
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${YELLOW}[!] $1 not found, installing...${NC}"
        apt-get update -qq && apt-get install -y "$2" -qq
    fi
}

# Function to run command with timeout and error handling
run_with_timeout() {
    local timeout_duration=$1
    local description=$2
    shift 2
    
    echo -e "${BLUE}[*] $description${NC}"
    
    if timeout "$timeout_duration" "$@"; then
        echo -e "${GREEN}[✓] $description completed${NC}"
        return 0
    else
        local exit_code=$?
        if [ $exit_code -eq 124 ]; then
            echo -e "${YELLOW}[!] $description timed out${NC}"
        else
            echo -e "${RED}[!] $description failed with exit code $exit_code${NC}"
        fi
        return $exit_code
    fi
}

# Phase 1: Initial Port Scan
echo -e "\n${GREEN}[+] Phase 1: Initial Port Discovery${NC}"
check_tool "nmap" "nmap"

run_with_timeout 120s "Quick port scan (top 1000 ports)" \
    nmap -T4 --top-ports 1000 -oN "$OUTPUT_DIR/quick_scan.txt" "$TARGET"

# Extract open ports for full scan
OPEN_PORTS=$(grep "^[0-9]" "$OUTPUT_DIR/quick_scan.txt" | grep "open" | cut -d'/' -f1 | tr '\n' ',' | sed 's/,$//')

if [ -z "$OPEN_PORTS" ]; then
    echo -e "${RED}[!] No open ports found. Exiting.${NC}"
    exit 1
fi

echo -e "${GREEN}[+] Found open ports: $OPEN_PORTS${NC}"

# Phase 2: Detailed Port Scan
echo -e "\n${GREEN}[+] Phase 2: Service Version Detection${NC}"

run_with_timeout 300s "Detailed service scan on open ports" \
    nmap -sV -sC -p "$OPEN_PORTS" -oN "$OUTPUT_DIR/detailed_scan.txt" -oX "$OUTPUT_DIR/detailed_scan.xml" "$TARGET"

# Phase 3: Web Enumeration (if HTTP/HTTPS ports are open)
echo -e "\n${GREEN}[+] Phase 3: Web Service Enumeration${NC}"

HTTP_PORTS=$(echo "$OPEN_PORTS" | tr ',' '\n' | grep -E '^(80|443|8000|8080|8443)$' | tr '\n' ' ')

if [ -n "$HTTP_PORTS" ]; then
    for port in $HTTP_PORTS; do
        if [ "$port" = "443" ] || [ "$port" = "8443" ]; then
            PROTOCOL="https"
        else
            PROTOCOL="http"
        fi
        
        URL="${PROTOCOL}://${TARGET}:${port}"
        echo -e "${BLUE}[*] Enumerating $URL${NC}"
        
        # Technology detection
        check_tool "whatweb" "whatweb"
        run_with_timeout 30s "Technology identification on port $port" \
            whatweb "$URL" -a 3 | tee "$OUTPUT_DIR/whatweb_${port}.txt"
        
        # Directory enumeration
        check_tool "gobuster" "gobuster"
        if [ -f "/usr/share/wordlists/dirb/common.txt" ]; then
            run_with_timeout 600s "Directory enumeration on port $port" \
                gobuster dir -u "$URL" -w /usr/share/wordlists/dirb/common.txt -t 20 \
                -o "$OUTPUT_DIR/gobuster_${port}.txt" 2>&1
        else
            echo -e "${YELLOW}[!] Wordlist not found, skipping directory enumeration${NC}"
        fi
        
        # Nikto scan
        check_tool "nikto" "nikto"
        run_with_timeout 300s "Nikto vulnerability scan on port $port" \
            nikto -h "$URL" -o "$OUTPUT_DIR/nikto_${port}.txt"
    done
else
    echo -e "${YELLOW}[!] No web ports found${NC}"
fi

# Phase 4: SMB Enumeration (if port 445 or 139 is open)
echo -e "\n${GREEN}[+] Phase 4: SMB Enumeration${NC}"

if echo "$OPEN_PORTS" | tr ',' '\n' | grep -qE '^(139|445)$'; then
    check_tool "enum4linux" "enum4linux"
    run_with_timeout 120s "SMB enumeration with enum4linux" \
        enum4linux -a "$TARGET" | tee "$OUTPUT_DIR/enum4linux.txt"
    
    check_tool "smbclient" "smbclient"
    run_with_timeout 30s "SMB share listing" \
        smbclient -L "//$TARGET" -N | tee "$OUTPUT_DIR/smbclient.txt"
else
    echo -e "${YELLOW}[!] No SMB ports found${NC}"
fi

# Phase 5: FTP Enumeration (if port 21 is open)
echo -e "\n${GREEN}[+] Phase 5: FTP Enumeration${NC}"

if echo "$OPEN_PORTS" | tr ',' '\n' | grep -q '^21$'; then
    echo -e "${BLUE}[*] Testing FTP anonymous login${NC}"
    run_with_timeout 10s "FTP anonymous access test" \
        bash -c "echo -e 'user anonymous\npass anonymous\nls\nquit' | nc -w 5 $TARGET 21" | tee "$OUTPUT_DIR/ftp_anon.txt"
else
    echo -e "${YELLOW}[!] FTP port not found${NC}"
fi

# Phase 6: DNS Enumeration (if port 53 is open)
echo -e "\n${GREEN}[+] Phase 6: DNS Enumeration${NC}"

if echo "$OPEN_PORTS" | tr ',' '\n' | grep -q '^53$'; then
    check_tool "dig" "dnsutils"
    run_with_timeout 10s "DNS zone transfer attempt" \
        dig @"$TARGET" ANY | tee "$OUTPUT_DIR/dns_query.txt"
else
    echo -e "${YELLOW}[!] DNS port not found${NC}"
fi

# Phase 7: Service-Specific Checks
echo -e "\n${GREEN}[+] Phase 7: Service-Specific Banner Grabbing${NC}"

for port in $(echo "$OPEN_PORTS" | tr ',' '\n'); do
    echo -e "${BLUE}[*] Banner grabbing on port $port${NC}"
    timeout 5s bash -c "echo '' | nc -v -n -w2 $TARGET $port" 2>&1 | tee "$OUTPUT_DIR/banner_${port}.txt"
done

# Generate summary report
echo -e "\n${GREEN}[+] Generating Summary Report${NC}"

SUMMARY_FILE="$OUTPUT_DIR/SUMMARY.txt"

cat > "$SUMMARY_FILE" << EOF
╔═══════════════════════════════════════════════════════════╗
║         AUTOMATED ENUMERATION SUMMARY REPORT              ║
╚═══════════════════════════════════════════════════════════╝

Target: $TARGET
Date: $(date)
Scan Duration: $SECONDS seconds

═══════════════════════════════════════════════════════════

OPEN PORTS:
$(cat "$OUTPUT_DIR/quick_scan.txt" | grep "^[0-9]" | grep "open")

═══════════════════════════════════════════════════════════

SERVICES DETECTED:
$(grep "^[0-9]" "$OUTPUT_DIR/detailed_scan.txt" | grep "open")

═══════════════════════════════════════════════════════════

WEB SERVICES:
$(find "$OUTPUT_DIR" -name "whatweb_*.txt" -exec echo "---" \; -exec cat {} \;)

═══════════════════════════════════════════════════════════

DISCOVERED DIRECTORIES/FILES:
$(find "$OUTPUT_DIR" -name "gobuster_*.txt" -exec cat {} \; 2>/dev/null | grep "Status: 200" | head -20)

═══════════════════════════════════════════════════════════

SMB INFORMATION:
$(head -50 "$OUTPUT_DIR/enum4linux.txt" 2>/dev/null || echo "No SMB enumeration performed")

═══════════════════════════════════════════════════════════

NEXT STEPS:
1. Review detailed scan results in $OUTPUT_DIR/
2. Investigate interesting services and their versions
3. Search for known exploits using searchsploit
4. Test identified web directories for vulnerabilities
5. Attempt default credentials on discovered services

═══════════════════════════════════════════════════════════
EOF

# Display summary
cat "$SUMMARY_FILE"

# Completion message
echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                Enumeration Complete!                      ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo -e "${YELLOW}[+] Results saved to: $OUTPUT_DIR/${NC}"
echo -e "${YELLOW}[+] Summary report: $OUTPUT_DIR/SUMMARY.txt${NC}"
echo -e ""
echo -e "${BLUE}Recommended next actions:${NC}"
echo -e "  1. Review $OUTPUT_DIR/SUMMARY.txt"
echo -e "  2. Investigate interesting findings in detail"
echo -e "  3. Run: searchsploit [SERVICE_NAME] [VERSION]"
echo -e "  4. Test discovered web directories manually"
echo -e "  5. Document findings in pentest_log.md"
echo -e ""

exit 0
