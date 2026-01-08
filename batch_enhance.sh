#!/bin/bash
# Batch enhance all WCAG reports
# Usage: ./batch_enhance.sh /path/to/reports/

REPORTS_DIR="${1:-.}"

echo "🔄 Enhancing WCAG reports in: $REPORTS_DIR"
echo ""

count=0
for report in "$REPORTS_DIR"/wcag_*.html; do
    # Skip already enhanced files
    if [[ "$report" == *"_enhanced.html" ]]; then
        continue
    fi
    
    if [ -f "$report" ]; then
        echo "Processing: $(basename "$report")"
        python enhance_report.py "$report"
        ((count++))
    fi
done

echo ""
echo "✅ Enhanced $count reports"
