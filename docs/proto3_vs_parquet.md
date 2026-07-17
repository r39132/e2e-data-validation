# Proto3 vs Apache Parquet — Format Comparison

This page compares Protocol Buffer 3 and Apache Parquet as formats: their design
goals, data models, encoding, schema evolution, and when to choose each.  It is
deliberately separate from the type-mapping focus of
[compatibility_analysis.md](compatibility_analysis.md), which answers the narrower
question of *how* proto3 types translate to Parquet when converting between the two.

**Related reading:**
- [Compatibility Analysis](compatibility_analysis.md) — proto3→Parquet type mapping
- [Recommendations](recommendations.md) — best practices for the conversion pipeline
- [Java Considerations](java_considerations.md) — Java library choices for each format

---

## 1. Format at a Glance

The fastest way to understand the difference is to see the same data in both formats.

Consider three `Person` records:

| id | name  | email             |
|----|-------|-------------------|
| 1  | Alice | alice@example.com |
| 2  | Bob   | bob@example.com   |
| 3  | Carol | *(not set)*       |

### 1.1 Proto3

Schema (`.proto` file — the schema is **not** embedded in the binary):

```proto
syntax = "proto3";

message Person {
  int32          id    = 1;
  string         name  = 2;
  optional string email = 3;
}
```

Binary file: a flat stream of varint-length-prefixed records.  Each record contains
only its own fields encoded as *tag–value* pairs, where the tag encodes the field
number and wire type.  An absent field (`email` for Carol) is simply omitted — zero
bytes consumed:

```
[varint len][encoded message bytes]

Record 1 (Alice, 28 bytes):
  1c  08 01  12 05 41 6c 69 63 65  1a 11 61 6c 69 63 65 40 65 78 61 6d 70 6c 65 2e 63 6f 6d
  ^28 ^id=1  ^name(5)="Alice"      ^email(17)="alice@example.com"

Record 2 (Bob, 24 bytes):
  18  08 02  12 03 42 6f 62  1a 0f 62 6f 62 40 65 78 61 6d 70 6c 65 2e 63 6f 6d
  ^24 ^id=2  ^name(3)="Bob"  ^email(15)="bob@example.com"

Record 3 (Carol, 9 bytes — email absent, zero bytes written):
  09  08 03  12 05 43 61 72 6f 6c
  ^9  ^id=3  ^name(5)="Carol"
```

Key properties:
- **Row-oriented**: all fields for one record are contiguous in the byte stream
- **Schema-free binary**: a reader needs the compiled `.proto` or a descriptor pool to decode the bytes
- **Sparse-friendly**: absent fields cost zero bytes regardless of field number
- **Streamable**: records can be appended indefinitely; no file finalisation step

### 1.2 Parquet

The same three records in a `.parquet` file.  All values for one column are stored
together in a *column chunk*, so a query that reads only `id` skips `name` and `email`
entirely without touching their bytes:

```
Magic: PAR1
│
├── Row Group 0  (3 rows)
│     ├── Column chunk: id     INT32    [1, 2, 3]
│     ├── Column chunk: name   STRING   ["Alice", "Bob", "Carol"]
│     └── Column chunk: email  STRING   ["alice@example.com", "bob@example.com", NULL]
│                                                                              ^^^^
│                              NULL stored via definition levels — distinct from ""
│
└── File Footer  (Thrift-encoded, written last)
      ├── Schema: message Person {
      │             required int32  id;
      │             required binary name  (STRING);
      │             optional binary email (STRING);
      │           }
      └── Row group metadata: 3 rows, byte offsets and sizes per column chunk
Magic: PAR1
```

Key properties:
- **Column-oriented**: all `id` values are adjacent; reading one column skips all others
- **Self-describing**: schema is embedded in the file footer — no external schema source needed
- **NULL-aware**: Carol's absent `email` is stored as a proper `NULL` via Parquet definition levels, not as `""`
- **Batch-oriented**: the footer is written last; the file cannot be read until writing is finalised

---

## 2. Design Goals

|  | **Proto3** | **Apache Parquet** |
|---|---|---|
| Primary purpose | Compact, versioned serialization for transport and storage of individual records | Columnar storage for large-scale analytics and data lakes |
| Optimised for | Write-one / read-one record at a time (RPC, streaming, event queues) | Read many rows but only a few columns (OLAP queries, aggregations) |
| Typical consumers | gRPC services, Kafka producers/consumers, mobile clients | Spark, Presto, Athena, BigQuery, Pandas, DuckDB |
| Schema location | External — in compiled generated code or a schema registry | Self-describing — schema stored in the file footer |
| File structure | Flat byte stream of length-delimited records | Hierarchical: row groups → column chunks → data pages |

The two formats solve complementary problems.  Proto3 excels at low-latency,
per-record serialization where schema is known at compile time.  Parquet excels at
batch analytics where only a fraction of columns are read per query.

---

## 3. Data Model

### 3.1 Orientation

**Proto3** is **row-oriented**.  Each serialized message contains all fields for one
record, laid out sequentially:

```
┌────────────────────────────────────────────┐
│ record 1: [field 1][field 2][field 3] ...  │
│ record 2: [field 1][field 2][field 3] ...  │
│ ...                                         │
└────────────────────────────────────────────┘
```

**Parquet** is **column-oriented**.  All values for one column are stored contiguously
within a row group, so a query touching two columns skips the rest entirely:

```
┌──────────────────────────────────────────────────┐
│ Row Group 1                                       │
│   column 1: [v1][v2][v3][v4] ...                 │
│   column 2: [v1][v2][v3][v4] ...                 │
│   column 3: [v1][v2][v3][v4] ...                 │
└──────────────────────────────────────────────────┘
│ Row Group 2                                       │
│   ...                                             │
└──────────────────────────────────────────────────┘
```

### 3.2 Type Systems

Proto3 has a **richer logical type system** tuned for message semantics:

| Category | Proto3 types |
|---|---|
| Integers | `int32`, `int64`, `uint32`, `uint64`, `sint32`, `sint64`, `fixed32`, `fixed64`, `sfixed32`, `sfixed64` |
| Floating point | `float`, `double` |
| Other scalars | `bool`, `string`, `bytes` |
| Composite | `message` (nested), `repeated` (list), `map<K,V>`, `oneof` (discriminated union), `enum` |
| Well-known types | `google.protobuf.Any`, `Struct`, `Timestamp`, `Duration`, `FieldMask`, … |

Parquet has a **smaller physical type set** extended by logical type annotations:

| Physical type | Logical annotations |
|---|---|
| `BOOLEAN` | — |
| `INT32` | `INT(8/16/32, signed/unsigned)`, `DATE`, `TIME`, `DECIMAL` |
| `INT64` | `INT(64, signed/unsigned)`, `TIMESTAMP`, `TIME` |
| `FLOAT` | — |
| `DOUBLE` | — |
| `BYTE_ARRAY` | `STRING` (UTF-8), `JSON`, `BSON`, `DECIMAL` |
| `FIXED_LEN_BYTE_ARRAY` | `UUID`, `DECIMAL` |
| Nested | `LIST`, `MAP`, `STRUCT` (via repeated groups) |

Notable **gaps**: Parquet has no native `enum`, `oneof`/union, `uint32`/`uint64`
(stored as signed but annotated), or well-known-type equivalents.  See
[compatibility_analysis.md](compatibility_analysis.md) for conversion strategies.

---

## 4. Wire Encoding

### 4.1 Proto3 wire format

Each field in a proto3 message is encoded as a *tag–value* pair.  The tag combines
the field number and a wire type:

| Wire type | Value | Used for |
|---|---|---|
| VARINT | 0 | `int32`, `int64`, `uint32`, `uint64`, `sint32`, `sint64`, `bool`, `enum` |
| I64 | 1 | `fixed64`, `sfixed64`, `double` |
| LEN | 2 | `string`, `bytes`, embedded messages, packed `repeated` |
| I32 | 5 | `fixed32`, `sfixed32`, `float` |

Fields **not present** in the binary are simply absent — unknown fields are skipped.
This makes proto3 files compact when fields are sparse.

`sint32`/`sint64` use **zigzag encoding** to encode negative integers efficiently.
`int32`/`int64` encode negative values as 10-byte varints (wasteful for small
negative numbers).

### 4.2 Parquet encoding

Parquet applies encoding **per column chunk**, choosing the most efficient strategy:

| Encoding | Best for |
|---|---|
| `PLAIN` | Low-cardinality raw values, fallback |
| `RLE_DICTIONARY` | Low-cardinality string or integer columns (e.g., enum-like values) |
| `DELTA_BINARY_PACKED` | Monotonically increasing integers (IDs, timestamps) |
| `DELTA_LENGTH_BYTE_ARRAY` | Variable-length strings with similar lengths |
| `BYTE_STREAM_SPLIT` | `FLOAT`/`DOUBLE` columns — rearranges bytes to improve compression ratio |

Parquet then applies a **second layer of compression** (Snappy, Zstd, LZ4, Gzip) over
the encoded column chunks.  The columnar layout means similar values are adjacent,
giving compressors much more to work with than row-oriented formats.

---

## 5. Schema

### 5.1 How schema is defined

**Proto3**: Schema lives in `.proto` source files and is compiled into language-specific
code by `protoc`.  The schema is NOT embedded in the binary file — a reader must have
the compiled generated code (or a descriptor pool) to interpret the bytes.

**Parquet**: Schema is **embedded in the file footer** as a Thrift-encoded
`FileMetaData` structure.  Any reader can inspect or decode the file without a separate
schema source.

### 5.2 Schema evolution

This is the most important practical difference for long-lived data pipelines:

| Scenario | Proto3 | Parquet |
|---|---|---|
| **Add a field/column** | ✅ Safe — old readers skip unknown field numbers | ✅ Safe — old readers return null for missing columns |
| **Remove a field/column** | ✅ Safe if the field number is `reserved` | ✅ Safe — readers requesting a removed column get null |
| **Rename a field** | ✅ Safe — wire format uses field numbers, not names | ❌ Breaking — column identity is the name, not a number |
| **Change a field type** | ⚠️ Limited safe pairs (e.g., `int32→int64`); most changes are breaking | ❌ Generally breaking |
| **Reuse a field number** | ❌ Never — corrupts old data | N/A |

The critical asymmetry: **proto3 uses field numbers as stable identity; Parquet uses
column names**.  Renaming a proto field is free at the wire level — you can rename
`user_id` to `userId` in the `.proto` without touching the binary.  Renaming a Parquet
column breaks every downstream reader that references it by name.

### 5.3 Nullability

**Proto3 (non-optional scalars)**: All scalar fields have implicit defaults (`0`, `""`,
`false`).  An absent field is indistinguishable from one explicitly set to its zero
value unless the field is declared `optional` (proto3 explicit presence) or lives inside
a `oneof`.

**Parquet**: Every column has an explicit **repetition level** and **definition level**,
allowing the format to distinguish `NULL` from a zero/empty value for any column.
`optional` proto3 fields map to nullable Parquet columns and preserve the
set/not-set distinction correctly.

---

## 6. Null and Missing Value Semantics

Proto3 and Parquet take fundamentally different approaches to absent data.  In proto3,
absence for non-optional scalars is **implicit** — an unset field returns the same zero
value as one explicitly set to `0`, `""`, or `false`, and there is no API to distinguish
them.  Parquet makes absence **explicit** through definition levels, giving every column
a three-way distinction: `NULL`, zero/empty, or a non-zero value.

| Scenario | Proto3 | Parquet |
|---|---|---|
| **Non-optional scalar not set** | Returns the type's zero default; `HasField` is not supported — the caller cannot detect absence | Non-nullable column has no `NULL`; a value must always be written |
| **`optional` scalar not set** | `HasField("f")` → `False`; `msg.f` still returns the zero default | Nullable column stores `NULL`, distinct from `""`, `0`, or `false` |
| **Message field not set** | `HasField("f")` → `False`; accessing the field returns an empty default message, not `None` | Nullable `STRUCT` column stores `NULL` |
| **`repeated` field empty** | Returns `[]`; cannot distinguish “never populated” from “explicitly cleared” | `LIST` column stores `[]`; a row never written stores `NULL` rather than `[]` |

---

## 7. Interoperability and Ecosystem

| | Proto3 | Parquet |
|---|---|---|
| **Query engines** | Most SQL engines require deserialization before querying; **Cloud Spanner** is a notable exception — it stores proto3 messages as a native column type and supports querying individual fields directly | DuckDB, Spark, Presto/Trino, Athena, BigQuery, Hive, Cloud Spanner |
| **Streaming** | Kafka (with Schema Registry), gRPC, Cloud Pub/Sub | Spark Structured Streaming and Flink write Parquet in micro-batches; Delta Lake and Apache Iceberg wrap Parquet files in a transaction log to add streaming semantics |
| **Object stores** | Any object store — bytes are opaque to the store itself; no native query support without deserialization | S3, GCS, ADLS — first-class integration via Hive, Spark, and Athena |
| **Schema registry** | Confluent Schema Registry, Buf Schema Registry | Apache Atlas, Hive Metastore, Glue Data Catalog |
| **Python** | `protobuf` package | `pyarrow`, `pandas`, `duckdb`, `fastparquet` |
| **Java** | `protobuf-java`, `protoc` | `parquet-java`, `parquet-protobuf` |
