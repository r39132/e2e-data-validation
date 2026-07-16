# Repeated Fields Dataset

## Purpose

Tests that `repeated` fields — proto3's mechanism for variable-length lists — convert
correctly to Parquet `LIST` types. The dataset covers three distinct cases: a list of
primitive integers, a list of strings, and a list of nested messages (each message
containing its own fields).

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

Each `repeated` field maps to a Parquet `LIST` column:

```
numbers: LIST<INT32>
tags:    LIST<STRING>
items:   LIST<STRUCT<name: STRING, price: DOUBLE>>
```

## Test Data

There is one record in the dataset. Its three fields test different list element types:

### `numbers` — list of int32 primitives
```json
[1, 2, 3, 5, 8, 13, 21]
```
A Fibonacci sequence. The non-trivial ordering (not sorted, not random) verifies that
**element order is preserved exactly** through serialization → Parquet conversion →
validation. If the converter re-ordered elements, the mismatch would be caught
immediately.

### `tags` — list of strings
```json
["important", "urgent", "review"]
```
Verifies that a `LIST<STRING>` round-trips without truncation, encoding corruption, or
element loss.

### `items` — list of nested messages
```json
[
  {"name": "Apple",  "price": 1.99},
  {"name": "Banana", "price": 0.59},
  {"name": "Orange", "price": 2.49}
]
```
Each element is a full `Item` message with two fields. This tests the most complex
`repeated` case: `LIST<STRUCT<STRING, DOUBLE>>`. The validator checks that both the
`name` string and the `price` double are preserved for each element, in order.

## What This Dataset Proves

| Aspect | Field that tests it |
|---|---|
| List of scalar primitives round-trips correctly | `numbers` |
| Element order is preserved | `numbers` (Fibonacci is order-sensitive) |
| List of strings round-trips correctly | `tags` |
| List of nested messages round-trips correctly | `items` |
| Nested field values inside list elements are preserved | `items[*].name`, `items[*].price` |

## Validation Points

✓ Array lengths match between PB3 and Parquet  
✓ Element order is identical  
✓ Primitive values in list elements are accurate  
✓ Nested message fields inside list elements are accurate  
