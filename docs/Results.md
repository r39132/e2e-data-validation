# Pipeline Results

## Execution Summary

All 8 datasets passed the full end-to-end pipeline (schema inference → PB3→Parquet conversion → field-by-field validation).

| Dataset | Schema Inference | PB3→Parquet | Validation | Overall |
|---|:---:|:---:|:---:|:---:|
| `basic_types` | ✓ | ✓ | ✓ | **PASS** |
| `nested_messages` | ✓ | ✓ | ✓ | **PASS** |
| `repeated_fields` | ✓ | ✓ | ✓ | **PASS** |
| `maps` | ✓ | ✓ | ✓ | **PASS** |
| `enums` | ✓ | ✓ | ✓ | **PASS** |
| `oneof` | ✓ | ✓ | ✓ | **PASS** |
| `optional_fields` | ✓ | ✓ | ✓ | **PASS** |
| `complex_nested` | ✓ | ✓ | ✓ | **PASS** |

**8/8 datasets passed (100%).**

**Related reading:**
- [Common Pitfalls and Conversion Bugs](common_pitfalls_and_conversion_bugs.md) — bugs uncovered during development and their fixes
- [Data Format Compatibility Analysis](Data_Format_Compatibility_Analysis.md) — full type compatibility table and recommendations
