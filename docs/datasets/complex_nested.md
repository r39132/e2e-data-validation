# Complex Nested Dataset

## Purpose

Tests that deeply nested structures — combining `repeated` fields, nested `message`
types, and `map` fields together in a multi-level hierarchy — convert correctly to
Parquet. This is the most structurally complex dataset in the suite and was the one
that exposed the schema inference bugs fixed during development.

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

There is one record. Its structure exercises four nesting levels simultaneously:
`LIST` of `STRUCT` (`departments`) containing a `LIST` of `STRUCT` (`employees`)
containing a `STRUCT` (`contact`) containing a `LIST` (`phones`), alongside a `MAP`
at the department level.

```json
{
  "company": "Tech Corp",
  "departments": [
    {
      "name": "Engineering",
      "employees": [
        {
          "name": "Alice",
          "age": 30,
          "contact": {
            "email": "alice@example.com",
            "phones": ["+1-555-0001", "+1-555-0002"]
          }
        },
        {
          "name": "Bob",
          "age": 35,
          "contact": {
            "email": "bob@example.com",
            "phones": ["+1-555-0003"]
          }
        }
      ],
      "metadata": {
        "location": "Building A",
        "floor": "3"
      }
    }
  ]
}
```

Alice has two phone numbers; Bob has one. This variation tests that `LIST<STRING>`
lengths are tracked per element, not globally. The `metadata` map at the department
level combines `MAP` and `STRUCT` in the same parent.

## What This Dataset Proves

| Aspect | Where tested |
|---|---|
| `LIST<STRUCT>` round-trips correctly | `departments` |
| `LIST<STRUCT<LIST<STRUCT>>>` (nested repeated messages) | `departments[*].employees` |
| `STRUCT` nested inside a `STRUCT` inside a `LIST` | `departments[*].employees[*].contact` |
| `LIST<STRING>` with varying lengths per parent element | `contact.phones` (Alice: 2, Bob: 1) |
| `MAP<STRING, STRING>` nested inside a `STRUCT` | `departments[*].metadata` |
| Schema inference handles 4+ levels of brace nesting | Entire message |

The schema inference bug that was fixed during development (bracket-counting parser)
was discovered specifically on this dataset. See
[Results and Analysis](../../Results_and_Analysis.md#2a-regex-could-not-handle-more-than-one-level-of-brace-nesting)
for details.

## Validation Points

✓ Four levels of nesting preserved  
✓ `LIST` lengths correct at every nesting level  
✓ Per-element `LIST` lengths independent (Alice's 2 phones ≠ Bob's 1 phone)  
✓ Nested `STRUCT` field values accurate at all depths  
✓ `MAP` inside a `STRUCT` inside a `LIST` round-trips correctly

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
