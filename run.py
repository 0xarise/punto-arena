#!/usr/bin/env python3
"""
Clean start script for Punto AI Web Game
"""
import os
import sys

# Check API keys
if not os.getenv('ANTHROPIC_API_KEY'):
    print("⚠️  WARNING: ANTHROPIC_API_KEY not set!")
    print("   Run: export ANTHROPIC_API_KEY='your-key'")

if not os.getenv('OPENAI_API_KEY'):
    print("⚠️  WARNING: OPENAI_API_KEY not set!")
    print("   Run: export OPENAI_API_KEY='your-key'")

# Import and run app
from app import app

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎮 PUNTO AI WEB GAME - STARTING")
    print("="*60)
    print(f"\n📁 Working directory: {os.getcwd()}")
    print(f"🌐 Server: http://127.0.0.1:8000")
    print(f"🤖 AI Models: Claude Sonnet, GPT-4o, Claude Opus")
    print(f"📊 Daily limit: 20 games\n")
    print("="*60)
    print("\n⏳ Starting Flask server...\n")

    # Run with explicit host and port (PORT 8000 to avoid AirPlay conflict)
    app.run(
        host='127.0.0.1',
        port=8000,
        debug=True,
        use_reloader=False  # Disable reloader to avoid port conflicts
    )
