#!/usr/bin/env php
<?php
/**
 * PHP Security Scanner
 *
 * This script scans PHP files for common security vulnerabilities
 * and coding standard violations.
 *
 * Usage: php php-security-scanner.php <directory> [--recursive] [--exclude=vendor,node_modules]
 *
 * @version 1.1.0
 */

class SecurityScanner {
    private array $vulnerabilities = [];
    private array $warnings = [];
    private int $fileCount = 0;
    private bool $recursive = false;
    private array $excludeDirs = ['vendor', 'node_modules', '.git'];

    private array $dangerousFunctions = [
        'eval', 'exec', 'system', 'shell_exec', 'passthru',
        'proc_open', 'popen', 'pcntl_exec', 'assert', 'create_function'
    ];

    private array $sqlKeywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP'];

    /**
     * Scan a directory for PHP files
     *
     * @param string $directory Directory path to scan
     * @throws InvalidArgumentException If directory doesn't exist or isn't readable
     */
    public function scanDirectory(string $directory): void {
        // Validate and sanitize directory path
        $directory = $this->validateDirectory($directory);

        // Get all PHP files
        $files = $this->findPhpFiles($directory);

        if (empty($files)) {
            $this->log("No PHP files found in: {$directory}");
            $this->generateReport();
            return;
        }

        // Scan each file
        foreach ($files as $file) {
            $this->scanFile($file);
            $this->fileCount++;
        }

        $this->generateReport();
    }

    /**
     * Validate directory path
     *
     * @param string $directory Directory path to validate
     * @return string Normalized absolute path
     * @throws InvalidArgumentException If directory is invalid
     */
    private function validateDirectory(string $directory): string {
        // Remove trailing slashes
        $directory = rtrim($directory, DIRECTORY_SEPARATOR);

        // Check if directory exists
        if (!file_exists($directory)) {
            throw new InvalidArgumentException("Directory does not exist: {$directory}");
        }

        // Check if it's actually a directory
        if (!is_dir($directory)) {
            throw new InvalidArgumentException("Path is not a directory: {$directory}");
        }

        // Check if directory is readable
        if (!is_readable($directory)) {
            throw new InvalidArgumentException("Directory is not readable: {$directory}");
        }

        // Get real path (resolves symlinks and relative paths)
        $realPath = realpath($directory);
        if ($realPath === false) {
            throw new InvalidArgumentException("Cannot resolve directory path: {$directory}");
        }

        return $realPath;
    }

    /**
     * Find all PHP files in directory (optionally recursive)
     *
     * @param string $directory Directory to search
     * @return array List of PHP file paths
     */
    private function findPhpFiles(string $directory): array {
        $pattern = $this->recursive
            ? $directory . '/**/*.php'
            : $directory . '/*.php';

        $files = glob($pattern, GLOB_BRACE);

        // Filter out excluded directories
        if (!empty($this->excludeDirs)) {
            $files = array_filter($files, function($file) {
                foreach ($this->excludeDirs as $excludeDir) {
                    if (strpos($file, DIRECTORY_SEPARATOR . $excludeDir . DIRECTORY_SEPARATOR) !== false) {
                        return false;
                    }
                }
                return true;
            });
        }

        return $files === false ? [] : $files;
    }

    /**
     * Set recursive scan mode
     */
    public function setRecursive(bool $recursive): void {
        $this->recursive = $recursive;
    }

    /**
     * Set directories to exclude from scan
     *
     * @param array $dirs List of directory names to exclude
     */
    public function setExcludeDirs(array $dirs): void {
        $this->excludeDirs = array_merge($this->excludeDirs, $dirs);
    }

    /**
     * Log a message
     */
    private function log(string $message): void {
        echo "[INFO] {$message}\n";
    }
    
    /**
     * Scan a single PHP file for security issues
     *
     * @param string $filePath Path to the PHP file
     * @throws RuntimeException If file cannot be read
     */
    public function scanFile(string $filePath): void {
        if (!file_exists($filePath)) {
            throw new RuntimeException("File not found: {$filePath}");
        }

        if (!is_readable($filePath)) {
            throw new RuntimeException("File is not readable: {$filePath}");
        }

        $content = file_get_contents($filePath);
        if ($content === false) {
            throw new RuntimeException("Failed to read file: {$filePath}");
        }

        $lines = explode("\n", $content);
        
        foreach ($lines as $lineNumber => $line) {
            $this->checkLine($filePath, $lineNumber + 1, $line);
        }
    }
    
    private function checkLine(string $file, int $lineNumber, string $line): void {
        // Check for dangerous functions
        foreach ($this->dangerousFunctions as $function) {
            if (preg_match('/\b' . $function . '\s*\(/i', $line)) {
                $this->addVulnerability($file, $lineNumber, $line, 
                    "CRITICAL: Use of dangerous function '$function'");
            }
        }
        
        // Check for SQL injection vulnerabilities
        if (preg_match('/\$_(GET|POST)\s*\[/', $line) && 
            preg_match('/' . implode('|', $this->sqlKeywords) . '/i', $line)) {
            $this->addVulnerability($file, $lineNumber, $line,
                "WARNING: Possible SQL injection with direct user input");
        }
        
        // Check for XSS vulnerabilities
        if (preg_match('/echo\s*\$_(GET|POST|COOKIE|SERVER)\s*\[/', $line) &&
            !preg_match('/htmlspecialchars|filter_var|esc_html/', $line)) {
            $this->addVulnerability($file, $lineNumber, $line,
                "WARNING: Possible XSS vulnerability - unescaped output");
        }
        
        // Check for file inclusion vulnerabilities
        if (preg_match('/(include|require)(_once)?\s*\$_(GET|POST)/', $line)) {
            $this->addVulnerability($file, $lineNumber, $line,
                "CRITICAL: Direct file inclusion with user input");
        }
        
        // Check for error suppression
        if (strpos($line, '@') !== false) {
            $this->addWarning($file, $lineNumber, $line,
                "INFO: Error suppression operator used - consider proper error handling");
        }
        
        // Check for global variables
        if (preg_match('/global\s+\$/', $line)) {
            $this->addWarning($file, $lineNumber, $line,
                "WARNING: Global variable usage - consider dependency injection");
        }
    }
    
    private function addVulnerability(string $file, int $line, string $code, string $message): void {
        $this->vulnerabilities[] = [
            'file' => $file,
            'line' => $line,
            'code' => trim($code),
            'message' => $message
        ];
    }
    
    private function addWarning(string $file, int $line, string $code, string $message): void {
        $this->warnings[] = [
            'file' => $file,
            'line' => $line,
            'code' => trim($code),
            'message' => $message
        ];
    }
    
    private function generateReport(): void {
        echo "PHP Security Scanner Report\n";
        echo "==========================\n\n";
        echo "Files scanned: {$this->fileCount}\n\n";
        
        if (empty($this->vulnerabilities) && empty($this->warnings)) {
            echo "✅ No security issues found!\n";
            return;
        }
        
        if (!empty($this->vulnerabilities)) {
            echo "🔴 CRITICAL VULNERABILITIES:\n";
            foreach ($this->vulnerabilities as $vuln) {
                echo "  File: {$vuln['file']}:{$vuln['line']}\n";
                echo "  Code: {$vuln['code']}\n";
                echo "  Issue: {$vuln['message']}\n\n";
            }
        }
        
        if (!empty($this->warnings)) {
            echo "🟡 WARNINGS:\n";
            foreach ($this->warnings as $warning) {
                echo "  File: {$warning['file']}:{$warning['line']}\n";
                echo "  Code: {$warning['code']}\n";
                echo "  Issue: {$warning['message']}\n\n";
            }
        }
        
        $criticalCount = count($this->vulnerabilities);
        $warningCount = count($this->warnings);
        
        echo "\nSUMMARY: {$criticalCount} critical issues, {$warningCount} warnings\n";
        
        if ($criticalCount > 0) {
            exit(1);
        }
    }
}

/**
 * Main execution
 */

// Display help if requested
if (in_array('--help', $argv) || in_array('-h', $argv)) {
    displayHelp();
    exit(0);
}

// Check if directory argument is provided
if ($argc < 2) {
    echo "Error: Missing directory argument\n\n";
    displayHelp();
    exit(1);
}

// Parse command line arguments
$directory = $argv[1];
$options = parseOptions(array_slice($argv, 2));

try {
    $scanner = new SecurityScanner();

    // Apply options
    if (isset($options['recursive'])) {
        $scanner->setRecursive(true);
    }

    if (isset($options['exclude'])) {
        $scanner->setExcludeDirs($options['exclude']);
    }

    // Run scan
    $scanner->scanDirectory($directory);

} catch (InvalidArgumentException $e) {
    echo "Error: " . $e->getMessage() . "\n";
    exit(1);
} catch (Exception $e) {
    echo "Unexpected error: " . $e->getMessage() . "\n";
    exit(1);
}

/**
 * Parse command line options
 *
 * @param array $args Command line arguments (excluding script name and directory)
 * @return array Parsed options
 */
function parseOptions(array $args): array {
    $options = [];

    foreach ($args as $arg) {
        if ($arg === '--recursive' || $arg === '-r') {
            $options['recursive'] = true;
        } elseif (strpos($arg, '--exclude=') === 0) {
            $excludeList = substr($arg, 10); // Remove '--exclude='
            $options['exclude'] = explode(',', $excludeList);
            $options['exclude'] = array_map('trim', $options['exclude']);
        }
    }

    return $options;
}

/**
 * Display help information
 */
function displayHelp(): void {
    $scriptName = basename(__FILE__);

    echo <<<HELP
PHP Security Scanner v1.1.0
============================

Scans PHP files for security vulnerabilities and coding standard violations.

USAGE:
    php {$scriptName} <directory> [OPTIONS]

ARGUMENTS:
    <directory>    Path to the directory to scan

OPTIONS:
    -r, --recursive          Scan subdirectories recursively
    --exclude=dirs           Comma-separated list of directories to exclude
                             (default: vendor,node_modules,.git)
    -h, --help               Display this help message

EXAMPLES:
    # Scan current directory
    php {$scriptName} .

    # Scan with recursive mode
    php {$scriptName} /path/to/project --recursive

    # Scan with custom exclusions
    php {$scriptName} /path/to/project --recursive --exclude=vendor,tests,cache

EXIT CODES:
    0    No critical issues found
    1    Critical vulnerabilities detected or error occurred

For more information, see: https://github.com/your-repo/php-security-scanner

HELP;
}
