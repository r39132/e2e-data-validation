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

---

## What the Tests Do and Don't Cover

The pipeline validator performs **field-by-field value comparison** between the original
`.pb3` binary and the converted `.parquet` file. This proves value fidelity but is
deliberately blind to structural and semantic constraints.

| Type | Why the test passes | What is actually lost (not tested) |
|---|---|---|
| `enum` | PB3 stores `2`, Parquet stores `2`, validator sees `2 == 2` ✓ | Symbolic name (`APPROVED`) is gone; Parquet won't reject an invalid integer |
| `oneof` | Inactive branch returns `0` in both PB3 and Parquet; `0 == 0` ✓ | Which branch was active is undetectable; mutual exclusivity is unenforced |
| Unset proto3 scalar | Both sides return the zero default (`""` / `0` / `false`); they match ✓ | Cannot distinguish "unset" from "explicitly set to zero" |
| Wire encoding variants | Logical value `42` is identical regardless of zigzag/fixed encoding ✓ | The original wire encoding choice is gone |
| Map key ordering | Both sides happen to have the same order at comparison time ✓ | A later read may return keys in a different order |
| `google.protobuf.Any` / `Struct` | **Not tested** — none of the 8 datasets use these types | Structure and type information would be lost; these are analytical findings only |

The 8/8 pass result is correct and meaningful: it proves that **no data values are
corrupted or dropped** during conversion. The ⚠️ and ❌ rows in the
[Data Format Compatibility Analysis](data_format_compatibility_analysis.md) describe
losses that a value comparator cannot detect — they require schema inspection, API
calls (`WhichOneof`, `HasField`), or dataset coverage that the current test suite does
not include.

**Related reading:**
- [Common Pitfalls and Conversion Bugs](common_pitfalls_and_conversion_bugs.md) — bugs uncovered during development and their fixes
- [Data Format Compatibility Analysis](data_format_compatibility_analysis.md) — full type compatibility table and recommendations
