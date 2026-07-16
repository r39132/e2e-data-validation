# Oneof Dataset

## Purpose

Tests that `oneof` fields — proto3's mutually exclusive field groups — convert to
Parquet without data loss in the field *values*, while documenting the structural
constraint that cannot be preserved.

## Protobuf Definition

```protobuf
message Oneof {
  string id = 1;

  oneof payload {
    string text_data    = 2;
    int32  numeric_data = 3;
    bool   flag_data    = 4;
  }
}
```

Proto3 guarantees that **at most one** field in a `oneof` group is set at a time.
Setting a second field automatically clears the first.

## Parquet Representation

Parquet has no discriminated-union type. Each `oneof` member becomes an independent
nullable column. In any given row, exactly one of the three payload columns will be
non-null; the other two will be null.

```
id:           STRING
text_data:    STRING  (nullable)
numeric_data: INT32   (nullable)
flag_data:    BOOLEAN (nullable)
```

## Test Data

There are three records — one per `oneof` branch — so every possible active field is
tested.

### Record 1 — `text_data` branch
```json
{"id": "rec1", "text_data": "Hello"}
```
| Column | Parquet value |
|---|---|
| `text_data` | `"Hello"` |
| `numeric_data` | `null` |
| `flag_data` | `null` |

### Record 2 — `numeric_data` branch
```json
{"id": "rec2", "numeric_data": 42}
```
| Column | Parquet value |
|---|---|
| `text_data` | `null` |
| `numeric_data` | `42` |
| `flag_data` | `null` |

### Record 3 — `flag_data` branch
```json
{"id": "rec3", "flag_data": true}
```
| Column | Parquet value |
|---|---|
| `text_data` | `null` |
| `numeric_data` | `null` |
| `flag_data` | `true` |

## What This Dataset Proves

| Aspect | Verified |
|---|---|
| The active `oneof` field value is preserved | ✓ |
| Inactive `oneof` fields are `null` in Parquet | ✓ |
| All three branch types (`string`, `int32`, `bool`) round-trip | ✓ |

## Known Semantic Loss

The **mutual exclusivity constraint is permanently lost** in Parquet. A Parquet reader
cannot tell whether `numeric_data = 0` means "this field was set to zero" or "this
field was not set" — both look identical. The proto `WhichOneof("payload")` information
is gone.

To preserve which branch was active, add a discriminator column before conversion:

```python
record["payload_case"] = message.WhichOneof("payload")  # e.g. "text_data"
```

See the [Proto3 vs Parquet Compatibility Analysis](../../Proto3_Parquet_Compatibility.md#21-oneof--mutual-exclusivity-lost)
for the full recommendation.

## Validation Points

✓ Active field value correct in all three records  
✓ Inactive fields are `null`  
✓ `id` string field alongside `oneof` fields round-trips correctly
- No native union type
- Multiple nullable columns (storage overhead)
- Manual validation needed

## Use Cases

Oneof is ideal for:
- Polymorphic data (different payload types)
- Event payloads with various structures
- API responses with multiple result types
- Configuration options (string vs number vs boolean)

## Best Practices

1. Keep oneof alternatives to reasonable number (< 10)
2. Document which field is set using a separate type/kind field
3. Consider alternatives like tagged unions if Parquet is primary storage
4. Validate oneof constraint after reading from Parquet
