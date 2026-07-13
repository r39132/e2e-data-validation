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

### Record 1: Maximum/Typical Values
- Tests large numbers and standard values
- Includes UTF-8 string: "Hello, Protobuf!"
- Binary data with readable content

### Record 2: Edge Cases
- Negative numbers
- Zero values
- Unicode string with non-ASCII characters: "Test 测试"
- Binary data with control characters

## Validation Points

✓ Numeric precision preserved  
✓ String encoding (UTF-8) maintained  
✓ Binary data integrity  
✓ Boolean values accurate  
✓ Type mappings correct

## Known Considerations

- Float precision may have minor rounding differences (within 1e-6 tolerance)
- Unsigned integers stored properly without overflow
- Empty strings vs null handled correctly
