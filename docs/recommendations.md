# Recommendations: Generic PB3 → Parquet Conversion

**Related reading:**
- [Compatibility Analysis](compatibility_analysis.md) — full type-level analysis with detailed rationale
- [Java Considerations](java_considerations.md) — how to implement a generic converter in Java
- [Codebase Guide](codebase.md) — how this project's Python pipeline is implemented

---

## Goal

The goal is to identify a **safe subset of Proto3 types** that can be converted to
Parquet using a single, generic conversion library — one in Python, one in Java —
without writing any per-dataset or per-schema custom code. The library must handle
any conforming proto3 schema at runtime using reflection and descriptor APIs alone.

This project's Python pipeline (`schema_inference.py` + `converter.py`) demonstrates
that this is achievable: it converts all 8 datasets without a single line of
per-dataset logic.

---

## Supported Types — Safe to Convert

The following proto3 types convert cleanly and are fully supported by a generic
converter. Values are preserved exactly and round-trip without loss:

| Proto3 type | Parquet representation | Notes |
|---|---|---|
| `int32`, `sint32`, `sfixed32` | `INT32` | Wire encoding variant lost; value preserved |
| `int64`, `sint64`, `sfixed64` | `INT64` | Same |
| `uint32`, `fixed32` | `UINT32` | |
| `uint64`, `fixed64` | `UINT64` | |
| `float` | `FLOAT` | |
| `double` | `DOUBLE` | |
| `bool` | `BOOLEAN` | |
| `string` | `STRING` (UTF-8) | |
| `bytes` | `BINARY` | |
| `optional T` | nullable column | Presence tracked via null |
| `repeated T` | `LIST<T>` | Any element type; order preserved |
| `map<K, V>` | `MAP<K, V>` | Key ordering non-deterministic in both formats |
| nested `message` | `STRUCT` | Arbitrary depth |
| `enum` | `INT32` | ⚠️ See below — values preserved, names lost |
| `oneof` | Independent nullable columns | ⚠️ See below — mutual exclusivity lost |

---

## Unsupported Types — Hard Blockers

The following types **cannot be generically converted** to Parquet without custom
pre-processing logic. They must be avoided in schemas intended for Parquet storage:

| Proto3 type | Why it cannot be generically converted | Reference |
|---|---|---|
| `google.protobuf.Any` | No fixed schema; the inner message type is unknown at write time without resolving the `type_url`. Structure and type information are permanently lost. | [compatibility_analysis.md §2.3](compatibility_analysis.md#23-googleprotobufany--structure-lost) |
| `google.protobuf.Struct` | Recursive `map<string, Value>` with no fixed schema; incompatible with Parquet's static schema requirement at write time. | [compatibility_analysis.md §2.4](compatibility_analysis.md#24-googleprotobufstruct--listvalue--no-clean-mapping) |
| `google.protobuf.ListValue` | Same recursive schema issue as `Struct`. | [compatibility_analysis.md §2.4](compatibility_analysis.md#24-googleprotobufstruct--listvalue--no-clean-mapping) |

---

## Supported with Known Semantic Loss

These types are **supported by the generic converter** — values are preserved and
validation passes — but structural metadata present in the proto is permanently lost
in Parquet. Downstream consumers must be aware of these limitations:

| Proto3 type | What is lost | Mitigation |
|---|---|---|
| `enum` | Symbolic names (`APPROVED`, `PENDING`) are not stored in Parquet; only the integer value is preserved. Parquet does not enforce valid enum ranges. | Store as string at write time, or maintain a schema registry. See [compatibility_analysis.md §2.2](compatibility_analysis.md#22-enum--names-and-range-validation-dropped). |
| `oneof` | Mutual exclusivity constraint is not enforceable in Parquet schema. Inactive branches are stored as their zero default (`0`, `""`, `false`), not `null`, making it impossible to distinguish "unset" from "set to zero". | Emit a `<group>_case` discriminator string column via `WhichOneof()`. See [compatibility_analysis.md §2.1](compatibility_analysis.md#21-oneof--mutual-exclusivity-lost) and [datasets/oneof.md](datasets/oneof.md). |
| Wire encoding variants | `sint32`, `fixed32`, `sfixed32` (and 64-bit equivalents) all become `INT32`/`INT64`. The specific wire encoding is lost. | Not reconstructable; acceptable for any use case that does not need to reproduce the exact proto binary. |
| Map key ordering | Neither proto3 nor Parquet guarantees map key order. | Use order-insensitive comparison for maps. |

---

## Language-Specific Implementation Notes

### Python (this project)

Use `message.DESCRIPTOR.fields` for reflection — no per-schema code is needed. The
`schema_inference.py` + `converter.py` modules are the reference implementation.
See [codebase.md](codebase.md) for a full walkthrough.

### Java

Use `DynamicMessage` + a `FileDescriptorSet` loaded at runtime. Never generate
per-schema Java classes in a generic pipeline. Always call
`ProtoWriteSupport.setWriteSpecsCompliant(true)`. See
[java_considerations.md §5](java_considerations.md#5-scalability-generic-vs-per-dataset-code)
for the full generic converter pattern including schema registry integration.
