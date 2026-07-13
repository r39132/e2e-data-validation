# Oneof Dataset

## Purpose

Tests `oneof` fields, which allow a message to have at most one field set from a group of fields (similar to a union type).

## Structure

```
Oneof
├── id: string
└── payload: oneof
    ├── text_data: string
    ├── numeric_data: int32
    └── flag_data: bool
```

## Protobuf Definition

```protobuf
message Oneof {
  string id = 1;
  
  oneof payload {
    string text_data = 2;
    int32 numeric_data = 3;
    bool flag_data = 4;
  }
}
```

## Parquet Representation

Oneof fields are challenging in Parquet because:
- Each alternative becomes a separate nullable column
- Only one field will have a value per record
- Other fields will be null

```
id: STRING
text_data: STRING (nullable)
numeric_data: INT32 (nullable)
flag_data: BOOLEAN (nullable)
```

## Test Data

### Record 1
- ID: "rec1"
- **text_data**: "Hello" (set)
- numeric_data: null
- flag_data: null

### Record 2
- ID: "rec2"
- text_data: null
- **numeric_data**: 42 (set)
- flag_data: null

### Record 3
- ID: "rec3"
- text_data: null
- numeric_data: null
- **flag_data**: true (set)

## Validation Points

✓ Only one oneof field is set per record  
✓ Set field has correct value  
✓ Unset fields are null  
✓ Oneof constraint maintained after conversion

## Design Trade-offs

**Protobuf Advantages:**
- Enforces mutual exclusivity
- Efficient binary encoding
- Clear API semantics

**Parquet Challenges:**
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
