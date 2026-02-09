#!/bin/bash

# Punto AI Web Game - Startup Script

echo "🎮 Starting Punto AI Web Game..."

# Activate virtual environment
source venv/bin/activate

# Check API keys
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  Warning: ANTHROPIC_API_KEY not set"
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  Warning: OPENAI_API_KEY not set"
fi

# Start Flask server
python app.py
