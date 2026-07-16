# Basic Types Dataset

## Purpose

Tests all Protocol Buffer 3 scalar primitive types to ensure proper conversion to Parquet format.

## Protobuf Types Covered

| Proto Type | Description | Parquet Mapping |
|------------|-------------|-----------------|
| `int32` | 32-bit signed integer | `INT32` |
| `int64` | 64-bit signed integer | `INT64` |
| `uint32` | 32-bit unsigned integer | `UINT32` |
| `uint64` | 64-bit unsigned integer | `UINT64` |
| `float` | Single precision float | `FLOAT` |
| `double` | Double precision float | `DOUBLE` |
| `bool` | Boolean value | `BOOLEAN` |
| `string` | UTF-8 encoded text | `STRING` |
| `bytes` | Raw binary data | `BINARY` |

## Test Cases

### Record 1: Overflow boundaries (maximum positive values)
Tests that each type correctly stores and round-trips its largest representable value.

> **Boundary column** — the canonical named constant (from C/C++ `<climits>` / `<cfloat>` headers and IEEE 754) that formally defines the limit being tested. Both Protobuf 3 and Parquet/PyArrow use the same underlying binary representations (two's complement integers and IEEE 754 floats), so these limits are identical and enforced in both formats. A value at `INT32_MAX` in the `.pb3` file will be stored as exactly `INT32_MAX` in the Parquet `INT32` column — no clamping, promotion, or loss occurs at either boundary.

| Field | Value | Boundary |
| `int32_field` | `2147483647` | `INT32_MAX` |
| `int64_field` | `9223372036854775807` | `INT64_MAX` |
| `uint32_field` | `4294967295` | `UINT32_MAX` |
| `uint64_field` | `18446744073709551615` | `UINT64_MAX` |
| `float_field` | `3.4028235e+38` | `FLT_MAX` |
| `double_field` | `1.7976931348623157e+308` | `DBL_MAX` |
| `bool_field` | `true` | — (only two values; both records cover both) |
| `string_field` | `"Hello, Protobuf!"` | — (no overflow/underflow concept) |
| `bytes_field` | `"binary data"` | — (no overflow/underflow concept) |

### Record 2: Underflow boundaries (minimum / most-negative values)
Tests that each type correctly stores and round-trips its most-negative (or smallest) representable value. The same format-compatibility guarantee applies: `INT32_MIN`, `INT64_MIN`, and `-FLT_MAX` / `-DBL_MAX` are enforceable and losslessly preserved in both pb3 and Parquet.

| Field | Value | Boundary | Notes |
|---|---|---|---|
| `int32_field` | `-2147483648` | `INT32_MIN` | |
| `int64_field` | `-9223372036854775808` | `INT64_MIN` | |
| `uint32_field` | `0` | `UINT32_MIN` | No negative range; 0 is the minimum |
| `uint64_field` | `0` | `UINT64_MIN` | No negative range; 0 is the minimum |
| `float_field` | `-3.4028235e+38` | `-FLT_MAX` | Most-negative finite 32-bit float; true IEEE 754 underflow (denormals) is a separate concern and not relevant for Parquet type-mapping validation |
| `double_field` | `-1.7976931348623157e+308` | `-DBL_MAX` | Most-negative finite 64-bit double |
| `bool_field` | `false` | — | |
| `string_field` | `"Test 测试"` | — | Unicode non-ASCII edge case |
| `bytes_field` | `0x00 0x01 0x02 0xFF` | — | Null byte and 0xFF edge case |

### Why no underflow test for `bool`, `string`, `bytes`
- **`bool`**: Only two values (`true` / `false`); both are covered across the two records.
- **`string`**: An unbounded text sequence; overflow and underflow have no meaningful definition.
- **`bytes`**: Same as `string` — unbounded binary sequence with no numeric range.

## Validation Points

✓ Numeric precision preserved  
✓ String encoding (UTF-8) maintained  
✓ Binary data integrity  
✓ Boolean values accurate  
✓ Type mappings correct

## Known Considerations

- Float precision: `FLT_MAX` stored in proto `float` (32-bit) and read back via PyArrow may have a rounding delta within 1e-30 of the original due to float32→float64 widening on read. The validator uses `float32` for the Parquet column so no precision loss occurs at the column level.
- `-FLT_MAX` / `-DBL_MAX` round-trip cleanly; IEEE 754 underflow (denormals, smallest positive non-zero) is deliberately not tested here because it is a serialization-layer concern rather than a Parquet type-mapping concern.
- Unsigned integer minimum (0) and maximum are both covered; there is no negative range to test.
- Empty strings vs null handled correctly (tested in the `optional_fields` dataset).
