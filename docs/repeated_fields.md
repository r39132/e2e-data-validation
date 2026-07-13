# Repeated Fields Dataset

## Purpose

Tests repeated fields (arrays/lists) with both primitive types and nested messages.

## Structure

```
RepeatedFields
├── numbers: repeated int32
├── tags: repeated string
└── items: repeated Item
    ├── name: string
    └── price: double
```

## Protobuf Definition

```protobuf
message RepeatedFields {
  repeated int32 numbers = 1;
  repeated string tags = 2;
  
  message Item {
    string name = 1;
    double price = 2;
  }
  repeated Item items = 3;
}
```

## Parquet Schema

Repeated fields map to Parquet `LIST` types:

```
numbers: LIST<INT32>
tags: LIST<STRING>
items: LIST<STRUCT<name: STRING, price: DOUBLE>>
```

## Test Data

- **Numbers**: Fibonacci sequence `[1, 2, 3, 5, 8, 13, 21]`
- **Tags**: `["important", "urgent", "review"]`
- **Items**: Shopping list with 3 items (Apple, Banana, Orange) and prices

## Validation Points

✓ Array lengths preserved  
✓ Element order maintained  
✓ Primitive array values accurate  
✓ Nested message arrays converted correctly  
✓ Empty arrays handled (if present)

## Performance Notes

- Repeated fields use efficient columnar storage in Parquet
- Large arrays are well-compressed
- Nested repeated fields may increase file size

## Use Cases

Common in:
- Time series data (repeated measurements)
- Multi-valued attributes (tags, categories)
- Collections of related objects (order items, log entries)
