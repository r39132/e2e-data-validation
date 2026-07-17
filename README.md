# E2E Data Validation

![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)
![PyArrow](https://img.shields.io/badge/PyArrow-14%2B-orange?logo=apache&logoColor=white)
![Protobuf](https://img.shields.io/badge/protobuf-7.x-brightgreen?logo=google&logoColor=white)
![Parquet](https://img.shields.io/badge/format-Parquet-blue?logo=apache&logoColor=white)
![License](https://img.shields.io/badge/license-Apache%202.0-blue?logo=apache&logoColor=white)

This project provides end-to-end testing for converting Protocol Buffer 3 (PB3) data to Apache Parquet format.

**📚 [Quick Start Guide](docs/QUICKSTART.md)** - Get started in 5 minutes

## Table of Contents

- [Project Structure](#project-structure)
- [Pipeline Data Flow](#pipeline-data-flow)
- [Test Datasets](#test-datasets)
- [Pipeline Steps](#pipeline-steps)
- [Recommendation: Generic PB3 → Parquet Conversion](#recommendation-generic-pb3--parquet-conversion)
- [Results and Analysis](#results-and-analysis)
- [Proto3 vs Parquet Compatibility](#proto3-vs-parquet-compatibility)
- [Proto3 vs Parquet Format Comparison](#proto3-vs-parquet-format-comparison)
- [Codebase Guide](#codebase-guide)
- [Usage](#usage)

---

## Project Structure <sup>[↑](#table-of-contents)</sup>

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
│   ├── proto3_vs_parquet.md  # Format comparison: design, encoding, schema evolution
│   └── README.md          # Docs index
└── pyproject.toml         # Project configuration
```

---

## Pipeline Data Flow <sup>[↑](#table-of-contents)</sup>

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

---

## Test Datasets <sup>[↑](#table-of-contents)</sup>

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

---

## Pipeline Steps <sup>[↑](#table-of-contents)</sup>

1. **Generate Datasets**: Create test data covering PB3 features
2. **Schema Inference**: Generate Parquet schema from .proto files
3. **Conversion**: Convert .pb3 files to Parquet format
4. **Validation**: Verify data integrity between PB3 and Parquet
5. **Reporting**: Generate success/failure reports

---

## Recommendation: Generic PB3 → Parquet Conversion <sup>[↑](#table-of-contents)</sup>

See **[Recommendations](docs/recommendations.md)** for the full analysis, but the headline findings are:

**✅ Safe to convert generically** (13 types): all scalar primitives, `optional`, `repeated`, `map`, nested `message`

**⚠️ Supported with semantic loss**: `enum` (names lost), `oneof` (mutual exclusivity lost)

**❌ Hard blockers — must be avoided**: `google.protobuf.Any`, `google.protobuf.Struct`, `google.protobuf.ListValue`

A single generic library (Python or Java) using reflection and descriptor APIs can handle any proto3 schema that avoids the ❌ types — no per-dataset custom code required.

---

## Results and Analysis <sup>[↑](#table-of-contents)</sup>

See **[Pipeline Results](docs/results.md)** for:
- Full pipeline execution summary (8/8 datasets pass)

See **[Common Pitfalls and Conversion Bugs](docs/common_pitfalls.md)** for:
- Bugs found during development, root causes, and fixes
- General landmines for any PB3→Parquet Python pipeline

---

## Proto3 vs Parquet Compatibility <sup>[↑](#table-of-contents)</sup>

See **[Java Considerations](docs/java_considerations.md)** for:
- How a Java/`parquet-java` implementation differs from this Python/PyArrow pipeline
- The `setWriteSpecsCompliant` flag, integer promotion risks, and library stack comparison

See **[Proto3 vs Parquet Data Type Compatibility Analysis](docs/compatibility_analysis.md)** for:
- Master compatibility table reconciling empirical and analytical findings
- Detailed analysis of problematic types (`oneof`, `enum`, `Any`, `Struct`)
- Recommendations on algorithms, libraries, and types to avoid
- Coverage gaps and next steps

---

## Proto3 vs Parquet Format Comparison <sup>[↑](#table-of-contents)</sup>

See **[Proto3 vs Parquet — Format Comparison](docs/proto3_vs_parquet.md)** for:
- Design goals: per-record transport (proto3) vs columnar analytics (Parquet)
- Data model: row-oriented vs column-oriented layout
- Type systems: proto3 rich logical types vs Parquet physical+annotation model
- Wire encoding: varint tag–value pairs vs per-column encoding strategies
- Schema evolution: field-number stability (proto3) vs name-based identity (Parquet)
- Null/missing value semantics
- Performance characteristics and ecosystem comparison
- Decision guide: when to use each, and the dual-format pipeline pattern

---

## Codebase Guide <sup>[↑](#table-of-contents)</sup>

See **[Codebase Guide](docs/codebase.md)** for:
- Architecture overview and data flow
- Module-by-module explanation (`generator.py`, `schema_inference.py`, `converter.py`, `validator.py`)
- Key algorithms: varint reading, bracket-counting proto parser, schema-from-proto
- Known limitations and their workarounds

---

## Usage <sup>[↑](#table-of-contents)</sup>

```bash
# Run the complete pipeline
jupyter notebook notebooks/e2e_conversion_validator.ipynb
```

The notebook will execute all 5 pipeline steps and generate a comprehensive report showing which datasets passed validation.