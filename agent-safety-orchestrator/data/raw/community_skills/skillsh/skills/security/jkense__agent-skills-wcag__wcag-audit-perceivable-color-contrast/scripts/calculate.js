#!/usr/bin/env node

/**
 * WCAG Contrast Ratio Calculator
 * Calculates contrast ratios for WCAG 2.1/2.2 compliance
 */

const fs = require('fs');
const path = require('path');

// Parse command line arguments
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const value = args[i + 1];
      if (value && !value.startsWith('--')) {
        options[key] = value;
        i++; // Skip next arg as it's the value
      } else {
        options[key] = true;
      }
    }
  }

  return options;
}

// Parse color from various formats (hex, rgb, hsl)
function parseColor(color) {
  if (!color) return null;

  // Remove spaces and convert to lowercase
  color = color.trim().toLowerCase();

  // Hex format (#RGB, #RRGGBB)
  if (color.startsWith('#')) {
    const hex = color.slice(1);
    if (hex.length === 3) {
      // #RGB -> #RRGGBB
      return {
        r: parseInt(hex[0] + hex[0], 16),
        g: parseInt(hex[1] + hex[1], 16),
        b: parseInt(hex[2] + hex[2], 16)
      };
    } else if (hex.length === 6) {
      return {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16)
      };
    }
  }

  // RGB format
  if (color.startsWith('rgb(') && color.endsWith(')')) {
    const values = color.slice(4, -1).split(',').map(v => parseInt(v.trim()));
    if (values.length === 3) {
      return { r: values[0], g: values[1], b: values[2] };
    }
  }

  // HSL format (simplified - just return as-is for now, would need HSL->RGB conversion)
  if (color.startsWith('hsl(') && color.endsWith(')')) {
    console.error('HSL color format not yet supported');
    process.exit(1);
  }

  return null;
}

// Calculate relative luminance
function getRelativeLuminance(color) {
  const { r, g, b } = color;

  // Convert to linear RGB values
  const toLinear = (value) => {
    const v = value / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };

  const rLinear = toLinear(r);
  const gLinear = toLinear(g);
  const bLinear = toLinear(b);

  // Calculate relative luminance
  return 0.2126 * rLinear + 0.7152 * gLinear + 0.0722 * bLinear;
}

// Calculate contrast ratio
function getContrastRatio(color1, color2) {
  const lum1 = getRelativeLuminance(color1);
  const lum2 = getRelativeLuminance(color2);

  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);

  return (lighter + 0.05) / (darker + 0.05);
}

// Check WCAG compliance
function checkCompliance(ratio, type = 'text') {
  const roundedRatio = Math.round(ratio * 100) / 100;

  if (type === 'non-text') {
    return {
      AA: roundedRatio >= 3.0,
      AAA: roundedRatio >= 3.0 // Non-text uses 3:1 for both AA and AAA
    };
  }

  // Text compliance
  return {
    AA: {
      normal: roundedRatio >= 4.5,
      large: roundedRatio >= 3.0
    },
    AAA: {
      normal: roundedRatio >= 7.0,
      large: roundedRatio >= 4.5
    }
  };
}

function formatColor(color) {
  return `rgb(${color.r}, ${color.g}, ${color.b})`;
}

function main() {
  const options = parseArgs();

  // Handle JSON input
  if (options.json) {
    try {
      const jsonInput = JSON.parse(options.json);
      options.foreground = jsonInput.foreground;
      options.background = jsonInput.background;
      options.type = jsonInput.type || 'text';
    } catch (e) {
      console.error('Invalid JSON input');
      process.exit(1);
    }
  }

  // Get colors
  const fgColor = parseColor(options.foreground || options.fg);
  const bgColor = parseColor(options.background || options.bg);

  if (!fgColor || !bgColor) {
    console.error('Usage: node calculate.js --foreground "#000000" --background "#FFFFFF" [--type text|non-text]');
    console.error('Or: node calculate.js --json \'{"foreground": "#000000", "background": "#FFFFFF"}\'');
    process.exit(1);
  }

  const type = options.type || 'text';
  const ratio = getContrastRatio(fgColor, bgColor);
  const compliance = checkCompliance(ratio, type);

  // Output JSON if requested
  if (options.json) {
    console.log(JSON.stringify({
      contrastRatio: Math.round(ratio * 100) / 100,
      compliance,
      colors: {
        foreground: formatColor(fgColor),
        background: formatColor(bgColor)
      }
    }, null, 2));
    return;
  }

  // Human-readable output
  console.log(`Contrast Ratio: ${Math.round(ratio * 100) / 100}:1`);

  if (type === 'non-text') {
    console.log(compliance.AA ? '✅ Non-text contrast: PASS' : '❌ Non-text contrast: FAIL');
  } else {
    console.log(compliance.AA.normal ? '✅ AA Normal Text: PASS' : '❌ AA Normal Text: FAIL');
    console.log(compliance.AA.large ? '✅ AA Large Text: PASS' : '❌ AA Large Text: FAIL');
    console.log(compliance.AAA.normal ? '✅ AAA Normal Text: PASS' : '❌ AAA Normal Text: FAIL');
    console.log(compliance.AAA.large ? '✅ AAA Large Text: PASS' : '❌ AAA Large Text: FAIL');
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  parseColor,
  getRelativeLuminance,
  getContrastRatio,
  checkCompliance
};