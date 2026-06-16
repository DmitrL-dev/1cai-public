#!/bin/bash
# Generate Architecture Diagram from Mermaid
# Requires: @mermaid-js/mermaid-cli
# Install: npm install -g @mermaid-js/mermaid-cli

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
DOCS_DIR="$PROJECT_ROOT/docs/architecture"
OUTPUT_FILE="$PROJECT_ROOT/Architecture_Connections_Diagram.png"

echo "🎨 Generating Architecture Diagram..."

# Check if mmdc is installed
if ! command -v mmdc &> /dev/null; then
    echo "❌ Error: mermaid-cli not found"
    echo "📦 Install: npm install -g @mermaid-js/mermaid-cli"
    exit 1
fi

# Extract first mermaid diagram from ARCHITECTURE_DIAGRAM.md
echo "📄 Extracting Mermaid code..."

# Create temporary file with just the mermaid code
TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

# Extract the main architecture diagram (first mermaid block)
sed -n '/```mermaid/,/```/p' "$DOCS_DIR/ARCHITECTURE_DIAGRAM.md" | \
    head -n -1 | tail -n +2 > "$TEMP_FILE"

if [ ! -s "$TEMP_FILE" ]; then
    echo "❌ Error: Could not extract Mermaid diagram"
    exit 1
fi

echo "✅ Mermaid code extracted"

# Generate PNG
echo "🖼️  Generating PNG..."

mmdc -i "$TEMP_FILE" \
     -o "$OUTPUT_FILE" \
     -t dark \
     -b transparent \
     -w 2400 \
     -H 1800

if [ -f "$OUTPUT_FILE" ]; then
    echo "✅ Diagram generated: $OUTPUT_FILE"
    echo "📊 Size: $(du -h "$OUTPUT_FILE" | cut -f1)"
else
    echo "❌ Error: Failed to generate diagram"
    exit 1
fi

echo ""
echo "🎉 Done! Architecture diagram updated."
echo "📁 File: $OUTPUT_FILE"
echo ""
echo "Next steps:"
echo "  git add Architecture_Connections_Diagram.png"
echo "  git commit -m 'docs: update architecture diagram to v5.0'"
echo "  git push"

