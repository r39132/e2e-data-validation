# Optional Fields Dataset

## Purpose

Tests the `optional` keyword in Proto3, which explicitly marks fields as optional and provides presence tracking.

## Structure

```
OptionalFields
├── required_field: string
├── optional_string: string (optional)
├── optional_int: int32 (optional)
└── optional_bool: bool (optional)
```

## Protobuf Definition

```protobuf
message OptionalFields {
  string required_field = 1;
  optional string optional_string = 2;
  optional int32 optional_int = 3;
  optional bool optional_bool = 4;
}
```

## Proto2 vs Proto3 Optional

**Proto3 (default):**
- No presence tracking by default
- Zero values (0, false, "") indistinguishable from unset
- No `has_*` methods

**Proto3 with `optional`:**
- Explicit presence tracking
- Can distinguish between set-to-zero and unset
- Generates `has_*` methods

## Parquet Schema

All fields are nullable in Parquet:

```
required_field: STRING (nullable: false in practice)
optional_string: STRING (nullable: true)
optional_int: INT32 (nullable: true)
optional_bool: BOOLEAN (nullable: true)
```

## Test Data

### Record 1 (Some fields set)
- required_field: "always present"
- **optional_string**: "sometimes here" (set)
- **optional_int**: 100 (set)
- optional_bool: null (unset)

### Record 2 (Minimal)
- required_field: "also present"
- optional_string: null (unset)
- optional_int: null (unset)
- optional_bool: null (unset)

## Validation Points

✓ Set optional fields have correct values  
✓ Unset optional fields are null in Parquet  
✓ Required fields always present  
✓ Null vs zero-value distinction maintained

## Key Differences

| Scenario | Proto3 Default | Proto3 Optional | Parquet |
|----------|---------------|-----------------|---------|
| Unset int32 | 0 (no presence) | null (has presence) | null |
| Set to 0 | 0 (no presence) | 0 (has presence) | 0 |
| Unset string | "" (no presence) | null (has presence) | null |
| Set to "" | "" (no presence) | "" (has presence) | "" |

## Use Cases

Use `optional` when:
- You need to distinguish "not set" from "set to default value"
- Migrating from Proto2 (had optional by default)
- Building APIs where null has meaning
- Form data with unsubmitted fields

## Migration Notes

- Proto3 added `optional` to ease Proto2 migration
- Without `optional`, use wrapper types (google.protobuf.Int32Value) for presence
- Parquet naturally supports nullability for all types
