# Nested Messages Dataset

## Purpose

Tests that a `message` field nested inside another `message` converts correctly to a
Parquet `STRUCT` type. This is the simplest nesting case — one level deep — and
establishes that field names, types, and values inside a `STRUCT` are fully preserved.

## Protobuf Definition

```protobuf
message NestedMessages {
  message Address {
    string street = 1;
    string city   = 2;
    int32  zip_code = 3;
  }

  string  name    = 1;
  Address address = 2;
}
```

## Parquet Schema

The nested `Address` message maps to a Parquet `STRUCT` column:

```
name:    STRING
address: STRUCT<
  street:   STRING,
  city:     STRING,
  zip_code: INT32
>
```

## Test Data

There is one record in the dataset:

```json
{
  "name": "John Doe",
  "address": {
    "street": "123 Main St",
    "city":   "Springfield",
    "zip_code": 12345
  }
}
```

The `address` field is a fully populated nested message. The validator checks that all
three inner fields (`street`, `city`, `zip_code`) survive the round-trip with their
correct types and values.

## What This Dataset Proves

| Aspect | Field that tests it |
|---|---|
| Nested message converts to `STRUCT` | `address` |
| String fields inside a struct are preserved | `address.street`, `address.city` |
| Integer fields inside a struct are preserved | `address.zip_code` |
| Top-level string field alongside a struct field | `name` |

## Validation Points

✓ `STRUCT` field names match the proto field names  
✓ All nested field values are accurate  
✓ Mixed types inside the struct (`STRING`, `INT32`) round-trip correctly
