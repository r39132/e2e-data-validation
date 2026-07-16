# Enums Dataset

## Purpose

Tests that proto3 `enum` fields convert correctly to Parquet `INT32` columns. Enum
values are integers at the wire level; the symbolic names (`PENDING`, `APPROVED`, etc.)
exist only in the `.proto` schema, not in the serialized data. This dataset confirms
that the integer values are preserved exactly while also documenting the semantic loss
that occurs.

## Protobuf Definition

```protobuf
message Enums {
  enum Status {
    UNKNOWN  = 0;
    PENDING  = 1;
    APPROVED = 2;
    REJECTED = 3;
  }

  enum Priority {
    LOW      = 0;
    MEDIUM   = 1;
    HIGH     = 2;
    CRITICAL = 3;
  }

  Status   status      = 1;
  Priority priority    = 2;
  string   description = 3;
}
```

## Parquet Schema

Both enum fields are stored as `INT32`. The name-to-integer mapping is not embedded in
the Parquet file or its metadata — a Parquet reader sees only numbers.

```
status:      INT32
priority:    INT32
description: STRING
```

## Test Data

There are two records. Together they cover four distinct enum values across the two
enum types and exercise non-zero, non-default values.

### Record 1
```json
{"status": 2, "priority": 3, "description": "Critical approval needed"}
```
| Field | Integer | Symbolic name |
|---|---|---|
| `status` | `2` | `APPROVED` |
| `priority` | `3` | `CRITICAL` |

### Record 2
```json
{"status": 1, "priority": 1, "description": "Awaiting review"}
```
| Field | Integer | Symbolic name |
|---|---|---|
| `status` | `1` | `PENDING` |
| `priority` | `1` | `MEDIUM` |

> **Note:** `UNKNOWN = 0` / `LOW = 0` (the proto3-required zero defaults) are not
> explicitly tested here because a missing or unset enum field already defaults to 0
> in proto3. Zero-value default behaviour is covered by the `optional_fields` dataset.

## What This Dataset Proves

| Aspect | Verified |
|---|---|
| Non-zero enum values round-trip as correct integers | ✓ |
| Two independent enum types in the same message | ✓ |
| Enum integers stored as `INT32` in Parquet | ✓ |

## Known Semantic Loss

Enum **symbolic names are not preserved** in Parquet. A Parquet reader sees `2` for
`status`, not `"APPROVED"`. The `.proto` schema is required to reconstruct the mapping.
For analytics workloads where names matter, consider converting enum fields to strings
before writing. See the
[Proto3 vs Parquet Compatibility Analysis](../Data_Format_Compatibility_Analysis.md#22-enum--names-and-range-validation-dropped)
for recommendations.

## Validation Points

✓ Integer values match the enum definitions in the `.proto` file  
✓ Both enum fields preserved independently  
✓ `description` string field alongside enum fields round-trips correctly
- Type discriminators
- Fixed option sets
- Flags and modes

## Migration Considerations

When the schema evolves:
- Adding enum values: Safe (append to end)
- Removing enum values: Dangerous (old data may have removed values)
- Renaming enum values: Safe (only names change, not integers)
