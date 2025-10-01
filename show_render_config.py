#!/usr/bin/env python
"""
Показывает текущую конфигурацию на Render
"""
import os
import sys

print("=" * 80)
print("CURRENT RENDER CONFIGURATION")
print("=" * 80)

print(f"\nPython: {sys.version}")
print(f"Executable: {sys.executable}")

print("\n--- Environment Variables ---")
print(f"RENDER: {os.environ.get('RENDER', 'Not Set')}")
print(f"PORT: {os.environ.get('PORT', 'Not Set')}")
print(f"DATABASE_URL: {'Set (hidden)' if os.environ.get('DATABASE_URL') else 'Not Set'}")
print(f"QBIT_HOST: {os.environ.get('QBIT_HOST', 'Not Set')}")
print(f"QBIT_PORT: {os.environ.get('QBIT_PORT', 'Not Set')}")

print("\n--- Gunicorn Config Check ---")
import os.path
if os.path.exists('gunicorn_config.py'):
    print("✓ gunicorn_config.py exists")
    with open('gunicorn_config.py', 'r') as f:
        for line in f:
            if 'timeout' in line and not line.strip().startswith('#'):
                print(f"  Config: {line.strip()}")
else:
    print("✗ gunicorn_config.py NOT FOUND!")

print("\n--- Command Line Arguments ---")
print(f"sys.argv: {sys.argv}")

print("\n--- Working Directory ---")
print(f"CWD: {os.getcwd()}")
print(f"Files: {os.listdir('.')[:20]}")

print("\n=" * 80)

