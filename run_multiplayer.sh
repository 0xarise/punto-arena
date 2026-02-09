#!/bin/bash

echo "🎮 Starting Punto AI Multiplayer..."

# Check API keys
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  WARNING: ANTHROPIC_API_KEY not set"
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  WARNING: OPENAI_API_KEY not set"
fi

# Activate venv
source venv/bin/activate

# Run multiplayer app
python app_multiplayer.py
