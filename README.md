# E2E Data Validation

![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)
![PyArrow](https://img.shields.io/badge/PyArrow-14%2B-orange?logo=apache&logoColor=white)
![Protobuf](https://img.shields.io/badge/protobuf-7.x-brightgreen?logo=google&logoColor=white)
![Parquet](https://img.shields.io/badge/format-Parquet-blue?logo=apache&logoColor=white)
![License](https://img.shields.io/badge/license-Apache%202.0-blue?logo=apache&logoColor=white)

This project provides end-to-end testing for converting Protocol Buffer 3 (PB3) data to Apache Parquet format.

**📚 [Quick Start Guide](docs/QUICKSTART.md)** - Get started in 5 minutes

## Project Structure

```
.
├── datasets/               # Test datasets with .proto, .json, and .pb3 files
├── src/                   # Source code for the pipeline
│   ├── generator.py       # Generate test datasets
│   ├── schema_inference.py # Infer Parquet schema from .proto
│   ├── converter.py       # Convert pb3 to parquet
│   └── validator.py       # Validate conversion results
├── notebooks/             # Jupyter notebooks
│   └── e2e_conversion_validator.ipynb  # Main pipeline execution notebook
├── docs/                  # Documentation
│   ├── datasets/          # Per-dataset documentation
│   ├── codebase.md        # Codebase guide
│   └── README.md          # Docs index
└── pyproject.toml         # Project configuration
```

## Pipeline Data Flow

```mermaid
graph TB
    Start([Start Pipeline]) --> Step1[Step 1: Generate Datasets]
    
    Step1 --> Gen1[Create .proto files]
    Step1 --> Gen2[Generate test data]
    Step1 --> Gen3[Compile .proto -> Python]
    Step1 --> Gen4[Serialize to .pb3 binary]
    Gen1 & Gen2 & Gen3 & Gen4 --> Step2
    
    Step2[Step 2: Infer Schema] --> Infer1[Parse .proto files]
    Infer1 --> Infer2[Map protobuf types -> Parquet types]
    Infer2 --> Infer3[Generate PyArrow schema]
    Infer3 --> Step3
    
    Step3[Step 3: Convert PB3 -> Parquet] --> Conv1[Read .pb3 binary]
    Conv1 --> Conv2[Deserialize protobuf messages]
    Conv2 --> Conv3[Transform to PyArrow tables]
    Conv3 --> Conv4[Write .parquet files]
    Conv4 --> Step4
    
    Step4[Step 4: Validate] --> Val1[Read both .pb3 and .parquet]
    Val1 --> Val2[Compare field-by-field]
    Val2 --> Val3{Data matches?}
    Val3 -->|Yes| Pass[✓ Validation passed]
    Val3 -->|No| Fail[✗ Validation failed]
    Pass & Fail --> Step5
    
    Step5[Step 5: Generate Report] --> Report1[Collect results from all datasets]
    Report1 --> Report2[Create summary DataFrame]
    Report2 --> Report3[Display pass/fail statistics]
    Report3 --> End([Pipeline Complete])
    
    style Step1 fill:#e1f5ff
    style Step2 fill:#fff4e1
    style Step3 fill:#f0e1ff
    style Step4 fill:#ffe1e1
    style Step5 fill:#e1ffe1
    style Pass fill:#90EE90
    style Fail fill:#FFB6C6
```

**Data Artifacts Generated:**
- **Input**: `.proto` schema definitions
- **Intermediate**: `.json` (test data), `*_pb2.py` (compiled modules), `.pb3` (binary)
- **Output**: `.parquet` (columnar format)
- **Validation**: Field-by-field comparison results

## Test Datasets

The pipeline generates 8 comprehensive datasets covering all major Protobuf3 features:

| Dataset | Features Tested | Files Generated |
|---------|----------------|-----------------|
| **[basic_types](docs/datasets/basic_types.md)** | All scalar primitives (int32, int64, uint32, uint64, float, double, bool, string, bytes) | `.proto`, `.json`, `.pb3`, `.parquet` |
| **[nested_messages](docs/datasets/nested_messages.md)** | Hierarchical message structures, embedded objects | `.proto`, `.json`, `.pb3`, `.parquet` |
| **[repeated_fields](docs/datasets/repeated_fields.md)** | Arrays/lists of primitives and messages | `.proto`, `.json`, `.pb3`, `.parquet` |
| **[maps](docs/datasets/maps.md)** | Key-value pairs with primitive and message values | `.proto`, `.json`, `.pb3`, `.parquet` |
| **[enums](docs/datasets/enums.md)** | Enumeration types with integer values | `.proto`, `.json`, `.pb3`, `.parquet` |
| **[oneof](docs/datasets/oneof.md)** | Union types (mutually exclusive fields) | `.proto`, `.json`, `.pb3`, `.parquet` |
| **[optional_fields](docs/datasets/optional_fields.md)** | Proto3 optional keyword, presence tracking | `.proto`, `.json`, `.pb3`, `.parquet` |
| **[complex_nested](docs/datasets/complex_nested.md)** | Deep nesting with multiple features combined | `.proto`, `.json`, `.pb3`, `.parquet` |

### File Types

Each dataset directory contains:

- **`.proto`** - Protocol Buffer schema definition (human-readable)
- **`.json`** - Test data in JSON format (human-readable)
- **`.pb3`** - Binary Protocol Buffer serialized data (source format)
- **`*_pb2.py`** - Compiled Python protobuf module (auto-generated)
- **`.parquet`** - Converted Parquet columnar data (target format)

Click on any dataset name above to see detailed documentation including schema definitions, Parquet mappings, validation points, and use cases.

## Pipeline Steps

1. **Generate Datasets**: Create test data covering PB3 features
2. **Schema Inference**: Generate Parquet schema from .proto files
3. **Conversion**: Convert .pb3 files to Parquet format
4. **Validation**: Verify data integrity between PB3 and Parquet
5. **Reporting**: Generate success/failure reports

## Results and Analysis

See **[Pipeline Results](docs/results.md)** for:
- Full pipeline execution summary (8/8 datasets pass)

See **[Common Pitfalls and Conversion Bugs](docs/common_pitfalls_and_conversion_bugs.md)** for:
- Bugs found during development, root causes, and fixes
- General landmines for any PB3→Parquet Python pipeline

## Proto3 vs Parquet Compatibility

See **[Proto3 vs Parquet Data Type Compatibility Analysis](docs/data_format_compatibility_analysis.md)** for:
- Master compatibility table reconciling empirical and analytical findings
- Detailed analysis of problematic types (`oneof`, `enum`, `Any`, `Struct`)
- Recommendations on algorithms, libraries, and types to avoid
- Coverage gaps and next steps

## Codebase Guide

See **[Codebase Guide](docs/codebase.md)** for:
- Architecture overview and data flow
- Module-by-module explanation (`generator.py`, `schema_inference.py`, `converter.py`, `validator.py`)
- Key algorithms: varint reading, bracket-counting proto parser, schema-from-proto
- Known limitations and their workarounds

## Usage

```bash
# Run the complete pipeline
jupyter notebook notebooks/e2e_conversion_validator.ipynb
```

The notebook will execute all 5 pipeline steps and generate a comprehensive report showing which datasets passed validation.