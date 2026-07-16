# Maps Dataset

## Purpose

Tests that `map<K, V>` fields — proto3's key-value dictionary type — convert correctly
to Parquet `MAP` types. The dataset covers three cases: a map with scalar integer
values, a map with string values, and a map with nested message values.

## Protobuf Definition

```protobuf
message Maps {
  map<string, int32> scores = 1;
  map<string, string> metadata = 2;

  message Value {
    double amount = 1;
    string currency = 2;
  }
  map<string, Value> prices = 3;
}
```

## Parquet Schema

Each `map<K, V>` field maps to a Parquet `MAP` column. Parquet represents maps
internally as a list of key-value struct pairs, so map iteration order is
non-deterministic in both formats — the validator compares maps order-insensitively.

```
scores:   MAP<STRING, INT32>
metadata: MAP<STRING, STRING>
prices:   MAP<STRING, STRUCT<amount: DOUBLE, currency: STRING>>
```

## Test Data

There is one record in the dataset.

### `scores` — map with scalar integer values
```json
{
  "Alice": 95,
  "Bob": 87,
  "Charlie": 92
}
```
Three string keys mapping to `int32` values. Tests that key-value associations survive
the round-trip and that all three entries are present in the Parquet output.

### `metadata` — map with string values
```json
{
  "version": "1.0",
  "author": "test",
  "status": "active"
}
```
Tests `MAP<STRING, STRING>` — the simplest and most common map type.

### `prices` — map with nested message values
```json
{
  "USD": {"amount": 100.0, "currency": "USD"},
  "EUR": {"amount": 85.0,  "currency": "EUR"}
}
```
Each value is a `Value` message with two fields. This is the most complex case:
`MAP<STRING, STRUCT<DOUBLE, STRING>>`. The validator checks that both `amount` and
`currency` are preserved for each key.

## What This Dataset Proves

| Aspect | Field that tests it |
|---|---|
| `MAP<STRING, INT32>` round-trips correctly | `scores` |
| `MAP<STRING, STRING>` round-trips correctly | `metadata` |
| `MAP<STRING, STRUCT>` round-trips correctly | `prices` |
| All keys and their associations are preserved | all three fields |
| Nested message fields inside map values are preserved | `prices[*].amount`, `prices[*].currency` |

## Known Considerations

- **Key ordering is non-deterministic** in both proto3 and Parquet. The validator
  compares maps as sets of key-value pairs, not as ordered sequences.
- **Keys are always unique** — proto3 guarantees this; duplicate keys in the source
  data would silently overwrite earlier entries.
- `MAP` columns in Parquet are read back by pandas as lists of `(key, value)` tuples,
  not Python dicts. The validator normalises these to dicts before comparison (see
  [Codebase Guide](../codebase.md)).

## Validation Points

✓ All keys present in Parquet output  
✓ Key-value associations correct  
✓ Scalar map values accurate  
✓ Nested message map values accurate  
✓ Map size matches between PB3 and Parquet  
