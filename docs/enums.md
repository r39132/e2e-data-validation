# Enums Dataset

## Purpose

Tests enumeration types, which define a fixed set of named integer values.

## Structure

```
Enums
├── status: Status (enum)
├── priority: Priority (enum)
└── description: string
```

## Protobuf Definition

```protobuf
message Enums {
  enum Status {
    UNKNOWN = 0;
    PENDING = 1;
    APPROVED = 2;
    REJECTED = 3;
  }
  
  enum Priority {
    LOW = 0;
    MEDIUM = 1;
    HIGH = 2;
    CRITICAL = 3;
  }
  
  Status status = 1;
  Priority priority = 2;
  string description = 3;
}
```

## Parquet Schema

Enums are stored as their underlying integer values:

```
status: INT32
priority: INT32
description: STRING
```

## Test Data

### Record 1
- Status: `APPROVED` (2)
- Priority: `CRITICAL` (3)
- Description: "Critical approval needed"

### Record 2
- Status: `PENDING` (1)
- Priority: `MEDIUM` (1)
- Description: "Awaiting review"

## Validation Points

✓ Enum values stored as integers  
✓ Integer values match enum definitions  
✓ Default values (0) handled correctly  
✓ Unknown enum values preserved

## Important Notes

- **Protobuf3 Rule**: First enum value must be 0 (used as default)
- Enum names are not stored in the data (only integer values)
- To reconstruct enum names, the original .proto schema is needed
- Adding new enum values is backward-compatible

## Use Cases

Enums are perfect for:
- Status codes and state machines
- Priority levels and categories
- Type discriminators
- Fixed option sets
- Flags and modes

## Migration Considerations

When the schema evolves:
- Adding enum values: Safe (append to end)
- Removing enum values: Dangerous (old data may have removed values)
- Renaming enum values: Safe (only names change, not integers)
