# Maps Dataset

## Purpose

Tests Protocol Buffer map fields, which are key-value pairs similar to dictionaries or hash tables.

## Structure

```
Maps
├── scores: map<string, int32>
├── metadata: map<string, string>
└── prices: map<string, Value>
    └── Value
        ├── amount: double
        └── currency: string
```

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

Maps are represented as Parquet `MAP` types or lists of key-value structs:

```
scores: MAP<STRING, INT32>
metadata: MAP<STRING, STRING>
prices: MAP<STRING, STRUCT<amount: DOUBLE, currency: STRING>>
```

## Test Data

- **Scores**: Student grades `{"Alice": 95, "Bob": 87, "Charlie": 92}`
- **Metadata**: Version info `{"version": "1.0", "author": "test", "status": "active"}`
- **Prices**: Currency rates `{"USD": {100.0, "USD"}, "EUR": {85.0, "EUR"}}`

## Validation Points

✓ Key-value associations preserved  
✓ Map size/count accurate  
✓ String keys handled correctly  
✓ Nested message values converted properly  
✓ Key uniqueness maintained

## Implementation Notes

- Protobuf maps guarantee unique keys
- Iteration order is not guaranteed
- Parquet represents maps as lists of key-value pairs
- Null values in maps need special handling

## Use Cases

Ideal for:
- Configuration settings
- Attribute-value pairs
- Lookup tables
- Metadata storage
- Flexible schemas with dynamic keys
