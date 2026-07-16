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

### Why `numeric_data` cannot reliably be `null` for inactive branches

A natural question is: since `optional` fields map to nullable Parquet columns and
`null` correctly represents "not set", why can't inactive `oneof` branches also be
stored as `null`?

The answer has two parts: one about the current pipeline, and one about the
fundamental constraint.

**1. How the current pipeline actually stores `oneof` scalars**

Neither `converter.py` nor `validator.py` calls `WhichOneof()`. Both use
`getattr(message, field.name)` for scalar fields, which returns the proto3 default
value for any field that is not the active branch:

```python
# What the converter does (simplified)
result["numeric_data"] = getattr(message, "numeric_data")
# Returns 0 when numeric_data is the inactive branch — not None
```

So for Record 1 (`text_data = "Hello"` is active), Parquet stores:

```
text_data    = "Hello"
numeric_data = 0       ← inactive branch; looks like "set to zero"
flag_data    = false   ← inactive branch; looks like "set to false"
```

This is the same behaviour as `optional` scalars in this pipeline: unset `optional`
fields are also stored as `""` / `0` / `false` (not `null`) because the converter
uses `getattr()` rather than `HasField()` for scalars. The difference is that
`optional` has only one field to consider — an unset `optional int32` showing `0` in
Parquet is unambiguous because there is nothing else competing for that column. With
`oneof`, three fields share one logical slot, so `numeric_data = 0` is ambiguous.

**2. The fix — and the remaining limitation after the fix**

The converter *could* use `WhichOneof()` to detect the active branch and store `null`
for the others:

```python
active = message.WhichOneof("payload")
result["text_data"]    = getattr(message, "text_data")    if active == "text_data"    else None
result["numeric_data"] = getattr(message, "numeric_data") if active == "numeric_data" else None
result["flag_data"]    = getattr(message, "flag_data")    if active == "flag_data"    else None
```

With this fix, Record 1 would store `numeric_data = null` (inactive) rather than `0`,
making it unambiguous. However, **one semantic constraint is still permanently lost**:
the Parquet schema has no mechanism to enforce that *at most one* of the three columns
is non-null per row. Proto3 enforces this at the language level; Parquet does not. A
downstream writer could produce a record with both `text_data` and `numeric_data`
non-null, and Parquet would accept it silently.

To preserve the active-branch metadata explicitly, add a discriminator column before
writing to Parquet:

```python
result["payload_case"] = message.WhichOneof("payload")  # e.g. "text_data", or None
```

`WhichOneof("payload")` is a proto API call that returns the **name** of whichever
field in the `oneof payload { ... }` group is currently set, as a string. If no
branch is set it returns `None`. Storing this string as an extra Parquet column means
a reader always knows exactly which branch was active, without having to guess from
the null pattern:

| `payload_case` | `text_data` | `numeric_data` | `flag_data` |
|---|---|---|---|
| `"text_data"` | `"Hello"` | `null` | `null` |
| `"numeric_data"` | `null` | `42` | `null` |
| `"flag_data"` | `null` | `null` | `true` |
| `None` | `null` | `null` | `null` |

The last row (`None`) shows the edge case where no branch was set — something that
is impossible to distinguish from "all branches inactive" using only null patterns.

See the [Proto3 vs Parquet Compatibility Analysis](../data_format_compatibility_analysis.md#21-oneof--mutual-exclusivity-lost)
for the full recommendation.

## Validation Points

✓ Active field value correct in all three records  
✓ Inactive fields are stored as proto3 defaults (0 / false / "") — validation passes  
✓ `id` string field alongside `oneof` fields round-trips correctly
