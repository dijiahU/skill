# PHP CS Fixer Configuration Guide

This reference guide provides ready-to-use PHP CS Fixer configurations for PHP projects following PSR-12 standards.

## What is PHP CS Fixer?

PHP CS Fixer is a tool that automatically fixes PHP code style issues, ensuring your code adheres to coding standards like PSR-12.

## Installation

```bash
composer require --dev friendsofphp/php-cs-fixer
```

## Basic Usage

```bash
# Fix all files in current directory
vendor/bin/php-cs-fixer fix

# Fix specific directory
vendor/bin/php-cs-fixer fix src/

# Dry run (show what would be changed)
vendor/bin/php-cs-fixer fix --dry-run --diff

# Fix specific file
vendor/bin/php-cs-fixer fix src/Controller/UserController.php
```

## Configuration File: `.php-cs-fixer.php`

Create a `.php-cs-fixer.php` file in your project root:

### Minimal Configuration (PSR-12)

```php
<?php

declare(strict_types=1);

$config = new PhpCsFixer\Config();

return $config->setRules([
        '@PSR12' => true,
    ])
    ->setRiskyAllowed(true)
    ->setFinder(
        PhpCsFixer\Finder::create()
            ->in(__DIR__)
            ->exclude('vendor')
            ->name('*.php')
            ->notName('*.blade.php')
    );
```

### Recommended Configuration (Enhanced)

```php
<?php

declare(strict_types=1);

$config = new PhpCsFixer\Config();

return $config
    ->setRiskyAllowed(true)
    ->setRules([
        '@PSR12' => true,
        '@PSR12:risky' => true,
        '@PHP74Migration' => true,
        '@PHP74Migration:risky' => true,

        // Additional rules
        'array_syntax' => ['syntax' => 'short'],
        'ordered_imports' => [
            'imports_order' => ['class', 'function', 'const'],
            'sort_algorithm' => 'alpha',
        ],
        'no_unused_imports' => true,
        'not_operator_with_successor_space' => true,
        'trailing_comma_in_multiline' => true,
        'phpdoc_scalar' => true,
        'unary_operator_spaces' => true,
        'binary_operator_spaces' => true,
        'blank_line_before_statement' => [
            'statements' => ['break', 'continue', 'declare', 'return', 'throw', 'try'],
        ],
        'phpdoc_single_line_var_spacing' => true,
        'phpdoc_var_without_name' => true,
        'class_attributes_separation' => [
            'elements' => [
                'const' => 'one',
                'method' => 'one',
                'property' => 'one',
            ],
        ],
        'method_argument_space' => [
            'on_multiline' => 'ensure_fully_multiline',
            'keep_multiple_spaces_after_comma' => true,
        ],
        'single_trait_insert_per_statement' => true,
        'declare_strict_types' => true,
        'no_empty_statement' => true,
        'no_leading_import_slash' => true,
        'no_leading_namespace_whitespace' => true,
        'no_whitespace_in_blank_line' => true,
        'return_type_declaration' => ['space_before' => 'none'],
        'single_blank_line_at_eof' => true,
        'single_quote' => true,
        'function_declaration' => true,
        'no_mixed_echo_print' => ['use' => 'echo'],
        'no_trailing_whitespace' => true,
        'no_trailing_whitespace_in_comment' => true,
        'no_useless_return' => true,
        'no_empty_comment' => true,
        'concat_space' => ['spacing' => 'one'],
        'function_typehint_space' => true,
        'single_line_comment_style' => ['comment_types' => ['hash']],
        'no_echo_call' => true,
    ])
    ->setFinder(
        PhpCsFixer\Finder::create()
            ->in(__DIR__)
            ->exclude('vendor')
            ->exclude('storage')
            ->exclude('bootstrap/cache')
            ->exclude('node_modules')
            ->name('*.php')
            ->notName('*.blade.php')
            ->notName('_ide_helper.php')
            ->notName('_ide_helper_models.php')
            ->notName('.phpstorm.meta.php')
            ->ignoreDotFiles(true)
            ->ignoreVCS(true)
    );
```

### Symfony Configuration

If you're using Symfony framework:

```php
<?php

declare(strict_types=1);

$config = new PhpCsFixer\Config();

return $config
    ->setRiskyAllowed(true)
    ->setRules([
        '@Symfony' => true,
        '@Symfony:risky' => true,
        '@PHP74Migration' => true,
        '@PHP74Migration:risky' => true,

        // Override specific Symfony rules
        'phpdoc_align' => ['align' => 'left'],
        'concat_space' => ['spacing' => 'one'],
    ])
    ->setFinder(
        PhpCsFixer\Finder::create()
            ->in(__DIR__)
            ->exclude('vendor')
            ->exclude('var')
    );
```

## Git Integration

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/sh

vendor/bin/php-cs-fixer fix --dry-run --diff

if [ $? -ne 0 ]; then
    echo "PHP CS Fixer found issues. Please run 'vendor/bin/php-cs-fixer fix' to fix them."
    exit 1
fi
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/php-cs-fixer.yml`:

```yaml
name: PHP CS Fixer

on:
    push:
        branches: [ main, develop ]
    pull_request:

jobs:
    php-cs-fixer:
        runs-on: ubuntu-latest

        steps:
            - name: Checkout code
              uses: actions/checkout@v4

            - name: Setup PHP
              uses: shivammathur/setup-php@v2
              with:
                  php-version: '8.2'
                  extensions: mbstring, xml, ctype, iconv, intl
                  coverage: none
                  tools: php-cs-fixer

            - name: Run PHP CS Fixer
              run: php-cs-fixer fix --dry-run --diff --verbose
```

### GitLab CI

Add to `.gitlab-ci.yml`:

```yaml
php-cs-fixer:
    stage: test
    image: php:8.2-cli
    before_script:
        - composer install --working-dir=/tmp
        - mv /tmp/vendor/bin/php-cs-fixer /usr/local/bin/php-cs-fixer
    script:
        - php-cs-fixer fix --dry-run --diff --verbose
    only:
        - merge_requests
        - main
        - develop
```

## VS Code Integration

Install extension:
- `junstyle.php-cs-fixer`

Configure in `.vscode/settings.json`:

```json
{
    "php-cs-fixer.executablePath": "${workspaceFolder}/vendor/bin/php-cs-fixer",
    "php-cs-fixer.config": ".php-cs-fixer.php",
    "php-cs-fixer.onsave": true,
    "php-cs-fixer.formatHtml": false,
    "editor.formatOnSave": true
}
```

## Common Rules Explained

### Array Syntax
- **Rule**: `array_syntax`
- **Purpose**: Convert `array()` to `[]`
- **Example**: `$arr = array(1, 2)` → `$arr = [1, 2]`

### Binary Operator Spaces
- **Rule**: `binary_operator_spaces`
- **Purpose**: Standardize spacing around operators
- **Example**: `$a=1+2` → `$a = 1 + 2`

### Declare Strict Types
- **Rule**: `declare_strict_types`
- **Purpose**: Add `declare(strict_types=1);` to all files
- **Benefit**: Enforces type safety

### No Unused Imports
- **Rule**: `no_unused_imports`
- **Purpose**: Remove unused use statements
- **Benefit**: Cleaner code

### Ordered Imports
- **Rule**: `ordered_imports`
- **Purpose**: Sort imports alphabetically
- **Benefit**: Easier to find imports

### Trailing Comma
- **Rule**: `trailing_comma_in_multiline`
- **Purpose**: Add trailing commas in multi-line arrays
- **Benefit**: Cleaner diffs when adding items

## Troubleshooting

### Issue: Configuration not being loaded
**Solution**: Ensure `.php-cs-fixer.php` is in project root, not in subdirectory

### Issue: Fixer breaks code
**Solution**: Run with `--dry-run` first to preview changes:
```bash
vendor/bin/php-cs-fixer fix --dry-run --diff
```

### Issue: Specific rule causing problems
**Solution**: Disable specific rule in config:
```php
'rule_name' => false,
```

### Issue: Too many changes
**Solution**: Run incrementally per directory:
```bash
vendor/bin/php-cs-fixer fix src/Controller
vendor/bin/php-cs-fixer fix src/Service
```

## Best Practices

1. **Commit the config file** - Keep `.php-cs-fixer.php` in version control
2. **Use dry-run in CI** - Don't auto-fix in CI pipelines
3. **Auto-fix on save** - Configure IDE to fix on save
4. **Review changes** - Always review auto-fixed code before committing
5. **Team consistency** - Ensure all team members use the same config
6. **Regular updates** - Keep PHP CS Fixer updated
7. **Incremental adoption** - Fix code incrementally, not all at once

## Additional Resources

- [Official Documentation](https://cs.symfony.com/)
- [PSR-12 Standard](https://www.php-fig.org/psr/psr-12/)
- [All Rules List](https://cs.symfony.com/doc/rules/)
