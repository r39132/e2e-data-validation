# Proto3 vs Parquet Data Type Compatibility Analysis

This document synthesises empirical pipeline results with analytical findings to give a
complete picture of how every Proto3 type behaves when converted to Apache Parquet, and
to prescribe the best practices for achieving reliable bidirectional compatibility.

**Related reading:**
- [Results and Analysis](Results_and_Analysis.md) — empirical 8/8 pipeline pass data, bugs found and fixed
- [Codebase Guide](docs/codebase.md) — how the pipeline code works

---

## 1. Master Compatibility Table

The table below reconciles two independent analyses: the empirical results from this
project's pipeline (Source B) and an earlier analytical design-document assessment
(Source A).  Where they diverged, the empirical result takes precedence for the
Python/PyArrow stack; Source A's warnings were largely Java-`parquet-java`-specific.

| Proto3 Feature | Parquet / PyArrow Representation | Bidirectional? | Notes |
|---|---|:---:|---|
| `int32`, `sint32`, `sfixed32` | `int32` | ✅ | Wire encoding (zigzag/fixed) is lost; logical value preserved |
| `int64`, `sint64`, `sfixed64` | `int64` | ✅ | Same as above |
| `uint32`, `fixed32` | `uint32` | ✅ | |
| `uint64`, `fixed64` | `uint64` | ✅ | |
| `float` | `float32` | ✅ | |
| `double` | `float64` | ✅ | |
| `bool` | `bool_` | ✅ | |
| `string` | `string` (UTF-8) | ✅ | |
| `bytes` | `binary` (`BYTE_ARRAY`) | ✅ | |
| `optional T` (proto3 explicit presence) | nullable column | ✅ | |
| `repeated T` (scalars & messages) | `LIST<T>` | ✅ | PyArrow always uses spec-compliant encoding |
| `map<K, V>` | `MAP<K, V>` | ✅ (order-insensitive) | Key ordering is non-deterministic in both formats |
| nested `message` | `STRUCT` | ✅ | |
| `enum` | `int32` | ⚠️ | Integer values preserved; symbolic names and range validation lost |
| `oneof` | Independent nullable columns | ⚠️ | Mutual exclusivity constraint is permanently lost |
| Unset proto3 scalar | Column value = zero default | ⚠️ | Shared proto3 limitation; not a Parquet regression |
| `google.protobuf.Any` | Falls back to raw `bytes` | ❌ | Structure and type URL are lost |
| `google.protobuf.Struct` / `ListValue` | No clean mapping | ❌ | Requires custom pre-processing; not tested in this pipeline |

---

## 2. Detailed Analysis of Problematic Types

### 2.1 `oneof` — mutual exclusivity lost

Parquet has no discriminated-union or variant type.  All members of a `oneof` group are
stored as independent nullable columns; the constraint that *exactly one* may be set
is not preserved.

```proto
// Proto3 — only one of these three can be set at a time
oneof payload {
  string text_value    = 2;
  int32  numeric_value = 3;
  bool   flag_value    = 4;
}
```

```
# Parquet row for text_value = "hello":
text_value="hello"   numeric_value=0   flag_value=false
```

A Parquet reader cannot distinguish `numeric_value = 0` (unset, defaulting to 0) from
`numeric_value = 0` (explicitly set to 0).  `WhichOneof()` metadata is permanently lost.

**Recommendation:** Add a synthetic discriminator column before writing:

```python
# Add before conversion
record["payload_case"] = message.WhichOneof("payload")  # e.g. "text_value"
```

The schema gains one `string` column per `oneof` group that lets downstream consumers
know which branch was set, at the cost of one extra column per group.

---

### 2.2 `enum` — names and range validation dropped

Parquet has no native enum type — the Parquet spec defines no enum logical annotation.
The only option is to store enum values as their underlying `int32`.  The
name-to-integer mapping lives only in the `.proto` file and is absent from the Parquet
schema and file metadata.  Additionally, Parquet places no constraint on valid integer
values, so a corrupt `int32` that has no corresponding enum variant will be silently
read back without error.

**Recommendation (pick one):**

| Option | How | Trade-off |
|---|---|---|
| Store as string | Convert `int32` → symbolic name string before writing | More readable; breaks numeric comparisons |
| Embed enum metadata | Write name→int mapping to Parquet file metadata (`schema.metadata`) | Transparent to most readers; metadata may be stripped |
| Keep `int32` + documentation | Leave as-is, document mapping in schema registry | Simplest; relies on operational discipline |

For analytics workloads the **string option is usually preferred** because it survives
schema evolution without a separate lookup table.

---

### 2.3 `google.protobuf.Any` — structure lost

`Any` wraps an arbitrary serialised message plus a `type_url`.  There is no native
Parquet type for this.  The Python protobuf library exposes the raw bytes; without
knowing the concrete type the bytes cannot be decoded into columns.

**Recommendation:** Avoid `Any` in messages that will be stored in Parquet.  If it
cannot be avoided:

1. Resolve the `type_url` to a concrete message class before conversion.
2. Deserialise the inner message and convert it as a `STRUCT`.
3. Add a `string` column for the `type_url` so consumers can identify the payload type.

---

### 2.4 `google.protobuf.Struct` / `ListValue` — no clean mapping

`Struct` is a JSON-like arbitrary key-value store backed by a `map<string, Value>` where
`Value` is itself a `oneof` over null/bool/number/string/list/struct.  This recursive
definition has no fixed schema, which is incompatible with Parquet's requirement for a
static schema at write time.

**Recommendation:** Serialize `Struct` to a JSON string column:

```python
from google.protobuf import json_format
record["my_struct"] = json_format.MessageToJson(msg.my_struct)
# Parquet column: string (JSON-encoded)
```

This preserves all information at the cost of making the content opaque to columnar
query engines.  For partial querying, Delta Lake / Iceberg with JSON variant types are
better targets than plain Parquet.

---

### 2.5 Wire encoding variants — collapsed to logical type

`sint32`, `fixed32`, and `sfixed32` all become `int32` in Parquet (same for 64-bit
variants).  The specific protobuf wire encoding (zigzag, fixed-width) is meaningful
only for serialization efficiency and does not affect the logical value.  This is
acceptable for any use case that does not need to reconstruct the exact proto binary.

---

### 2.6 Proto3 scalar field presence — shared limitation

In proto3, an unset scalar field is indistinguishable from a field explicitly set to its
zero value (`0`, `""`, `false`).  Parquet non-nullable columns have the same limitation.
This is a proto3 design constraint, not a Parquet regression.  Use `optional` (proto3
explicit presence) for fields where absence must be tracked; these become nullable
columns in Parquet and round-trip correctly.

---

## 3. Recommendations

### 3.1 Algorithm: always derive schema from `.proto`, not from data

**Do this:**

```python
# schema_inference.py approach — parses the .proto spec directly
schema = ProtoToParquetSchemaInference().infer_schema(proto_file)
```

**Not this:**

```python
# Inferring schema by scanning data values
schema = pa.Schema.from_pandas(dataframe)  # may upcast int32 → int64
```

Inferring from data causes integer promotion (e.g. `int32 → int64` when PyArrow
conservatively widens small samples) and loses nullability information.  The empirical
results confirm that schema-from-proto preserves exact widths for all 15 scalar types.

---

### 3.2 Algorithm: varint-prefixed length-delimited binary format

Standard Protobuf serializers write multiple messages to a single file using a
length-delimited format: each record is preceded by a varint encoding its byte length.
Always read `.pb3` files with a varint loop, not `split(b'\n')`:

```python
def _read_varint(f) -> int | None:
    result, shift = 0, 0
    while True:
        b = f.read(1)
        if not b:
            return None
        byte = b[0]
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result
        shift += 7

with open(pb3_file, 'rb') as f:
    while (length := _read_varint(f)) is not None:
        msg.ParseFromString(f.read(length))
```

See [src/converter.py](src/converter.py) and [src/validator.py](src/validator.py) for
the production implementation.

---

### 3.3 Algorithm: bracket-counting for `.proto` parsing

Regex-based `.proto` parsing breaks on deeply nested messages (two or more levels of
`message { message { ... } }` nesting).  Use a bracket-counting loop to find the
matching closing brace at arbitrary depth:

```python
depth = 1
i = body_start
while i < len(content) and depth > 0:
    if content[i] == '{':
        depth += 1
    elif content[i] == '}':
        depth -= 1
    i += 1
message_body = content[body_start:i - 1]
```

Then strip nested message blocks from the body before parsing field declarations, so
inner message fields do not appear as spurious top-level columns.  See
[src/schema_inference.py](src/schema_inference.py) for the full implementation.

---

### 3.4 Language and library recommendations

| Layer | Recommended | Avoid | Reason |
|---|---|---|---|
| Schema inference | Python + PyArrow (direct from `.proto`) | `parquet-java` schema inference from data | Exact widths; no legacy non-compliant LIST/MAP encodings |
| Serialization | `protobuf` Python package (v3.x or v4/v5 via `protoc`) | protobuf v7.x C-extension (`_upb`) without version-checking | v7 `FieldDescriptor` does not expose `.label` as instance attribute; see [Results and Analysis](Results_and_Analysis.md) |
| Parquet write | `pyarrow.parquet.write_table` | `fastparquet` for complex nested types | PyArrow has first-class `STRUCT`, `LIST`, `MAP` support; fastparquet's nested type support is incomplete |
| Parquet read | `pyarrow.parquet.read_table` | pandas alone | Pandas converts `LIST` columns to numpy arrays and `MAP` columns to lists of tuples; always normalise before comparison (see [src/validator.py](src/validator.py)) |
| Enum handling | Store as string OR use schema registry | Raw `int32` without documentation | Name loss is a real operational risk |

---

### 3.5 Types to avoid in Parquet-bound proto schemas

| Type | Severity | Alternative |
|---|---|---|
| `google.protobuf.Any` | ❌ Hard blocker | Concrete typed messages; or `bytes` + `type_url` string column |
| `google.protobuf.Struct` | ❌ Hard blocker | JSON string column; or structured schema with known fields |
| `google.protobuf.ListValue` | ❌ Hard blocker | `repeated` concrete type instead |
| `oneof` (without discriminator column) | ⚠️ Semantic loss | Add `<group>_case: string` discriminator before conversion |
| `enum` (when names matter downstream) | ⚠️ Semantic loss | Convert to string at write time, or store mapping in file metadata |
| Maps with message values and ordering requirements | ⚠️ Ordering loss | Accept order-insensitive comparison, or sort keys deterministically before write |

---

## 4. Coverage Gaps

The 8 datasets in this project validate the types marked ✅ and ⚠️ in the master table
empirically.  The following types are **not yet covered** and remain analytical findings
only:

| Uncovered type | Risk | Recommended next step |
|---|---|---|
| `google.protobuf.Any` | ❌ Structure lost | Add `any_field` dataset; implement `type_url`-aware converter |
| `google.protobuf.Struct` / `ListValue` | ❌ No clean mapping | Add `wkt_struct` dataset; implement JSON-string fallback |
| `oneof` with discriminator column | ⚠️ Currently not preserved | Extend converter to emit `<group>_case` column |
| `enum` stored as string | ⚠️ Currently `int32` only | Add string-enum option to `schema_inference.py` |

---

## 5. Summary

The Python / PyArrow stack is cleaner than the Java `parquet-java` stack for this
conversion:

- `repeated` and `map` always use spec-compliant encoding — no flag required.
- Integer widths are preserved exactly when schema is derived from `.proto`.
- All 15 primitive scalar types round-trip without loss.

The three genuine problem areas are **`oneof`** (semantic loss, fixable with a
discriminator column), **`enum`** (name loss, fixable at write time), and the **Well
Known Types** `Any`, `Struct`, and `ListValue` (structural incompatibility, require
custom handling or avoidance).

See [Results and Analysis](Results_and_Analysis.md) for the full empirical evidence and
[Codebase Guide](docs/codebase.md) for how the pipeline implements these algorithms.
