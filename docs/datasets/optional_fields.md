# Optional Fields Dataset

## Purpose

Tests the `optional` keyword introduced in proto3, which adds **explicit field
presence tracking** — the ability to distinguish between "field not set" and "field
set to its zero value". This is one of the cleaner proto→Parquet mappings: `optional`
fields become nullable columns, and `null` in Parquet faithfully represents an unset
field.

## Protobuf Definition

```protobuf
message OptionalFields {
  string          required_field  = 1;
  optional string optional_string = 2;
  optional int32  optional_int    = 3;
  optional bool   optional_bool   = 4;
}
```

### Proto3 presence tracking: default vs `optional`

| Scenario | Proto3 default field | Proto3 `optional` field | Parquet column |
|---|---|---|---|
| Field not set | `0` / `""` / `false` (indistinguishable from set-to-zero) | `null` | `null` |
| Field set to zero value | `0` / `""` / `false` | `0` / `""` / `false` | `0` / `""` / `false` |

Without `optional`, proto3 cannot represent absence for scalar fields — unset and
set-to-zero look identical. With `optional`, the `HasField()` API and a nullable
Parquet column preserve the distinction.

## Parquet Schema

```
required_field:  STRING  (non-nullable)
optional_string: STRING  (nullable)
optional_int:    INT32   (nullable)
optional_bool:   BOOLEAN (nullable)
```

## Test Data

Two records cover both extremes: all optional fields populated, and all optional
fields absent.

### Record 1 — optional fields set
```json
{
  "required_field":  "always present",
  "optional_string": "sometimes here",
  "optional_int":    100
}
```
`optional_bool` is absent from the JSON (unset in proto), so it becomes `null` in
Parquet. `optional_string` and `optional_int` are set and carry real values.

### Record 2 — all optional fields absent
```json
{
  "required_field": "also present"
}
```
All three `optional` fields are absent → all three are `null` in Parquet.
`required_field` is present in both records, confirming it is never null.

## What This Dataset Proves

| Aspect | Verified |
|---|---|
| Set `optional` fields carry their values through to Parquet | ✓ |
| Unset `optional` fields become `null` in Parquet (not zero) | ✓ |
| `required_field` is non-null in every record | ✓ |
| Mixed presence within a single record (some set, some unset) | ✓ (Record 1) |
| All optional fields simultaneously unset | ✓ (Record 2) |

## Validation Points

✓ Set optional field values are accurate  
✓ Unset optional fields are `null` in Parquet  
✓ `required_field` is always non-null  
✓ Null vs zero-value distinction is maintained

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
