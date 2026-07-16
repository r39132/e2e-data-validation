# Complex Nested Dataset

## Purpose

Tests deeply nested structures combining multiple Protobuf features: nested messages, repeated fields, and maps together in a realistic hierarchy.

## Structure

```
ComplexNested
├── company: string
└── departments: repeated Department
    ├── name: string
    ├── employees: repeated Person
    │   ├── name: string
    │   ├── age: int32
    │   └── contact: ContactInfo
    │       ├── email: string
    │       └── phones: repeated string
    └── metadata: map<string, string>
```

## Protobuf Definition

```protobuf
message ComplexNested {
  message Person {
    string name = 1;
    int32 age = 2;
    
    message ContactInfo {
      string email = 1;
      repeated string phones = 2;
    }
    ContactInfo contact = 3;
  }
  
  message Department {
    string name = 1;
    repeated Person employees = 2;
    map<string, string> metadata = 3;
  }
  
  string company = 1;
  repeated Department departments = 2;
}
```

## Parquet Schema

This creates a deeply nested columnar structure:

```
company: STRING
departments: LIST<STRUCT<
  name: STRING,
  employees: LIST<STRUCT<
    name: STRING,
    age: INT32,
    contact: STRUCT<
      email: STRING,
      phones: LIST<STRING>
    >
  >>,
  metadata: MAP<STRING, STRING>
>>
```

## Test Data

**Company:** Tech Corp

**Engineering Department:**
- Alice (30)
  - Email: alice@example.com
  - Phones: ["+1-555-0001", "+1-555-0002"]
- Bob (35)
  - Email: bob@example.com
  - Phones: ["+1-555-0003"]
- Metadata: {"location": "Building A", "floor": "3"}

## Validation Points

✓ Three levels of nesting preserved  
✓ Repeated fields at multiple levels accurate  
✓ Nested structs maintain integrity  
✓ Maps within structs converted correctly  
✓ Field paths accessible in Parquet

## Complexity Analysis

**Nesting Depth:** 4 levels  
**Total Field Types:**
- 6 strings
- 1 int32
- 1 repeated message (departments)
- 1 repeated message (employees)
- 1 repeated primitive (phones)
- 1 map (metadata)

## Performance Implications

**Protobuf Benefits:**
- Compact binary encoding
- Schema evolution support
- Fast serialization

**Parquet Benefits:**
- Columnar storage (great for analytics)
- Excellent compression on repeated values
- Predicate pushdown for filtering

**Trade-offs:**
- Deep nesting increases Parquet complexity
- May impact query performance if accessing deeply nested fields
- Consider flattening for analytics workloads

## Real-World Scenarios

This structure represents:
- **HR Systems**: Company → Departments → Employees → Contacts
- **E-commerce**: Orders → Line Items → Products → Variants
- **IoT**: Facilities → Devices → Sensors → Readings
- **Logging**: Systems → Services → Instances → Events

## Best Practices

1. **Limit nesting depth** to 3-4 levels when possible
2. **Denormalize** frequently queried fields to top level
3. **Use maps sparingly** in nested contexts
4. **Consider alternatives** like separate tables for very complex hierarchies
5. **Profile queries** to ensure acceptable performance

## Schema Evolution

Adding fields is safe:
- New optional fields at any level
- New map entries
- New array elements

Risky changes:
- Removing nested fields
- Changing field types
- Restructuring hierarchy
