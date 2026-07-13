# Nested Messages Dataset

## Purpose

Tests nested message structures to verify that hierarchical data is correctly converted to Parquet's struct types.

## Structure

```
NestedMessages
├── name: string
└── address: Address
    ├── street: string
    ├── city: string
    └── zip_code: int32
```

## Protobuf Definition

```protobuf
message NestedMessages {
  message Address {
    string street = 1;
    string city = 2;
    int32 zip_code = 3;
  }
  
  string name = 1;
  Address address = 2;
}
```

## Parquet Schema

Nested messages map to Parquet `STRUCT` types:

```
name: STRING
address: STRUCT<
  street: STRING,
  city: STRING,
  zip_code: INT32
>
```

## Test Data

- Person: "John Doe"
- Address: "123 Main St, Springfield, 12345"

## Validation Points

✓ Struct field names preserved  
✓ Nested field values accurate  
✓ Type hierarchy maintained  
✓ Null handling for optional nested messages

## Use Cases

This pattern appears in:
- User profiles with embedded address/contact info
- Product data with nested specifications
- Log records with structured metadata
