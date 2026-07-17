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

## 1. Design Goals

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

## 2. Data Model

### 2.1 Orientation

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

### 2.2 Type Systems

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

## 3. Wire Encoding

### 3.1 Proto3 wire format

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

### 3.2 Parquet encoding

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

## 4. Schema

### 4.1 How schema is defined

**Proto3**: Schema lives in `.proto` source files and is compiled into language-specific
code by `protoc`.  The schema is NOT embedded in the binary file — a reader must have
the compiled generated code (or a descriptor pool) to interpret the bytes.

**Parquet**: Schema is **embedded in the file footer** as a Thrift-encoded
`FileMetaData` structure.  Any reader can inspect or decode the file without a separate
schema source.

### 4.2 Schema evolution

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

### 4.3 Nullability

**Proto3 (non-optional scalars)**: All scalar fields have implicit defaults (`0`, `""`,
`false`).  An absent field is indistinguishable from one explicitly set to its zero
value unless the field is declared `optional` (proto3 explicit presence) or lives inside
a `oneof`.

**Parquet**: Every column has an explicit **repetition level** and **definition level**,
allowing the format to distinguish `NULL` from a zero/empty value for any column.
`optional` proto3 fields map to nullable Parquet columns and preserve the
set/not-set distinction correctly.

---

## 5. Performance Characteristics

| Dimension | Proto3 | Parquet |
|---|---|---|
| **Single-record read latency** | Very low — deserialize one length-delimited record | High — must load at minimum one page (~1 MB row group header) |
| **Full-table scan** | High I/O — must read all fields even if only one is needed | Low I/O — columnar layout skips unneeded columns |
| **Point lookup** | N/A natively (no row index) | Possible with row-group statistics + row-group skipping |
| **Compression ratio** | Moderate — varint packing, no cross-record compression | High — column similarity + dictionary/RLE + block compression |
| **Write throughput** | Very high — sequential append of length-delimited records | Moderate — must buffer a full row group before flushing |
| **Streaming writes** | Natural — append one record at a time | Awkward — Parquet files are closed/immutable once written |

---

## 6. Null / Missing Value Semantics

| Scenario | Proto3 behaviour | Parquet behaviour |
|---|---|---|
| Field not set (non-optional scalar) | Returns zero default (`0`, `""`, `false`); cannot detect absence | Column stores NULL if written with null; non-nullable column has no NULL |
| Field not set (`optional` scalar) | `HasField()` → `False`; `msg.field` → zero default | Nullable column stores NULL |
| Field not set (message type) | `HasField()` → `False` | Nullable STRUCT column stores NULL |
| Repeated field empty | Returns empty list; indistinguishable from absent | LIST column stores empty list `[]` |

---

## 7. Interoperability and Ecosystem

| | Proto3 | Parquet |
|---|---|---|
| **Query engines** | Not directly queryable — must deserialize first | DuckDB, Spark, Presto/Trino, Athena, BigQuery, Hive |
| **Streaming** | Kafka (with Schema Registry), gRPC, Pub/Sub | Delta Lake (microbatch), Iceberg streaming writes |
| **Object stores** | Any (bytes are opaque) | S3, GCS, ADLS — first-class support via Hive/Spark/Athena |
| **Schema registry** | Confluent Schema Registry, Buf Schema Registry | Apache Atlas, Hive Metastore, Glue Data Catalog |
| **Python** | `protobuf` package | `pyarrow`, `pandas`, `duckdb`, `fastparquet` |
| **Java** | `protobuf-java`, `protoc` | `parquet-java`, `parquet-protobuf` |

---

## 8. When to Use Each

### Use Proto3 when:

- Serializing messages for **network transport** (gRPC, REST with binary bodies)
- Publishing to **event streams** (Kafka, Pub/Sub, Kinesis) where consumers receive
  individual records
- **Mobile / embedded** scenarios where binary size and parse speed matter
- Schema must **evolve frequently** without coordinating with all consumers at once
  (field-number stability)
- The consumer needs **all fields** for every record (row-oriented access is optimal)

### Use Parquet when:

- Storing data in a **data lake** for analytics queries
- Workloads access only a **subset of columns** across many rows (OLAP)
- Data will be queried by **Spark, Athena, Presto, DuckDB, BigQuery**
- **Compression ratio** is important (columnar layout compresses much better)
- Data is written in **batches** rather than record by record

### Use both (this project's pattern):

Proto3 is often the **source of truth** for operational data (events, service outputs),
and Parquet is the **analytical copy**.  The conversion pipeline in this project
(schema inference → PB3→Parquet → validation) is the standard pattern for this
architecture.

```
Producers → proto3 (Kafka / gRPC) → Conversion pipeline → Parquet (S3 / GCS)
                                                                    ↓
                                              Spark / Athena / DuckDB queries
```

See [recommendations.md](recommendations.md) for safe type subsets and best practices
for operating this pipeline in production.
