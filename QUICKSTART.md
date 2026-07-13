# Quick Start Guide

Get up and running in minutes:

```bash
# 1. Ensure you have pyenv and protoc installed
# macOS: brew install pyenv protobuf
# Linux: Install via your package manager

# 2. Set up Python version
pyenv install 3.11.7
pyenv local 3.11.7

# 3. Install uv (fast Python package installer)
pip install uv

# 4. Install project dependencies
uv pip install -e .

# 5. Launch Jupyter and run the pipeline
jupyter notebook notebooks/pipeline.ipynb
```

## Helpful uv Commands

```bash
# Install dependencies from pyproject.toml
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"

# Add a new package
uv pip install package-name

# Upgrade a package
uv pip install --upgrade package-name

# List installed packages
uv pip list

# Create a virtual environment (if not using pyenv)
uv venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Sync dependencies (installs exactly what's in pyproject.toml)
uv pip sync

# Compile dependencies to requirements.txt
uv pip compile pyproject.toml -o requirements.txt

# Fast install from requirements.txt
uv pip install -r requirements.txt
```

## Why uv?

- **10-100x faster** than pip for package installation
- Drop-in replacement for pip commands
- Better dependency resolution
- Built in Rust for maximum performance

## Next Steps

1. Run the pipeline notebook to generate and test all datasets
2. Check the `datasets/` directory for generated files
3. Review individual dataset documentation in `docs/`
4. Examine validation results and reports
