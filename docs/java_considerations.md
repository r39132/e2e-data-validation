# Java Considerations for PB3 → Parquet Conversion

This document explains how a Java implementation of the same PB3→Parquet pipeline
would differ from the Python/PyArrow implementation documented in this project.

**Related reading:**
- [Compatibility Analysis](compatibility_analysis.md) — full type compatibility table (format-level; applies to both languages)
- [Common Pitfalls](common_pitfalls.md) — Python-specific bugs and fixes
- [Codebase Guide](codebase.md) — how the Python pipeline is implemented

---

## Summary

The type-compatibility table in [compatibility_analysis.md](compatibility_analysis.md)
is **format-level** — it describes what Parquet can and cannot represent, regardless
of which language writes the file. The ⚠️ and ❌ rows apply equally to Java.

The differences are in the **tooling layer**: which libraries to use, which flags to
set, and which failure modes to watch for.

---

## 1. Schema Inference

| | Python (this project) | Java |
|---|---|---|
| Approach | Custom bracket-counting `.proto` parser (`schema_inference.py`) | `parquet-proto` reads the proto descriptor at runtime via `ProtoSchemaConverter` |
| Integer widths | Exact widths preserved (schema-from-proto) | Exact widths preserved when using `ProtoParquetWriter` with a descriptor |
| Risk of upcasting | Low — schema is derived from the `.proto` spec | Present if schema is inferred from data (e.g. via `AvroParquetWriter`) rather than from the descriptor |
| Nested message resolution | Manual prefix-walking in `_resolve_type` | Handled automatically by the descriptor API |

**Java recommendation:** Always use `ProtoParquetWriter` with an explicit
`MessageDescriptor` rather than inferring schema from data values. Inferring from data
can silently upcast `int32` → `int64`.

---

## 2. `repeated` and `map` — the Biggest Java-Specific Risk

This is where Java diverges most significantly from PyArrow.

`parquet-java` (`parquet-mr`) has **two LIST/MAP encoding modes**:

| Mode | How to enable | Parquet spec compliant? | PyArrow readable? |
|---|---|---|---|
| Legacy (default in older versions) | Default | ❌ No | ⚠️ Sometimes |
| Spec-compliant | `ProtoWriteSupport.setWriteSpecsCompliant(true)` | ✅ Yes | ✅ Yes |

PyArrow always writes spec-compliant encoding. A file written by Java in **legacy
mode** may produce read errors or silently wrong data when read by PyArrow, Arrow
Flight, or DuckDB. Always set:

```java
ProtoWriteSupport.setWriteSpecsCompliant(true);
```

This was the "conditional hedge" in the original analytical design document (Source A)
that the Python empirical results (Source B) did not need — because PyArrow has no
legacy mode.

---

## 3. Integer Promotion

In PyArrow, `int32` stays `int32` when schema is derived from `.proto`. In Java,
if schema inference falls back to scanning data values (e.g. via Avro or a generic
writer), PyArrow-equivalent conservative widening may upcast small integers to `int64`.

**Fix:** Use `ProtoParquetWriter` with an explicit proto `Descriptor` — the Java
equivalent of `ProtoToParquetSchemaInference().infer_schema(proto_file)`.

---

## 4. Reading Parquet Back in Java

When reading Parquet files back in Java:

| Column type | Java / `parquet-proto` returns | Equivalent Python issue |
|---|---|---|
| `LIST` | `List<T>` (Java generics) | numpy array (fixed by `_normalize_value`) |
| `MAP` | `Map<K, V>` | list of tuples (fixed by `dict()` conversion) |
| `STRUCT` | Nested proto message | handled by `_message_to_dict` recursion |

Java's `parquet-proto` returns proper typed collections, so the numpy/tuple
normalisation issues from [Common Pitfalls §3c](common_pitfalls.md#3c-pandas-returns-non-native-types-for-parquet-compound-columns)
do not apply. However, map key ordering remains non-deterministic in both languages.

---

## 5. Library Stack Comparison

| Layer | Python (this project) | Java equivalent |
|---|---|---|
| Schema from `.proto` | `ProtoToParquetSchemaInference` (custom) | `ProtoSchemaConverter` (`parquet-protobuf`) |
| Write Parquet | `pyarrow.parquet.write_table` | `ProtoParquetWriter` (`parquet-mr`) |
| Read Parquet | `pyarrow.parquet.read_table` | `ParquetReader` / `ProtoParquetReader` |
| Proto serialization | `protobuf` Python package 7.x | `com.google.protobuf` Java library |
| Length-delimited stream | Custom varint loop | `CodedInputStream.readDelimitedFrom` |
| Validate | Custom `DataValidator` | Custom comparator or Hamcrest matchers |

---

## 6. `oneof`, `enum`, `Any`, `Struct` — Same Semantic Losses

These are format-level constraints, not language-level:

| Type | Java behaviour | Python behaviour |
|---|---|---|
| `oneof` | Flattened to independent nullable columns | Same |
| `enum` | Stored as `INT32`; names lost | Same |
| `google.protobuf.Any` | Raw bytes; structure lost | Same |
| `google.protobuf.Struct` | No fixed schema; no clean mapping | Same |

The recommendations in [compatibility_analysis.md](compatibility_analysis.md) (discriminator
columns for `oneof`, string conversion for `enum`, avoid `Any`/`Struct`) apply equally
to Java.

---

## 7. The `_upb` Bug is Python-Specific

The `FieldDescriptor.label` instance-attribute bug documented in
[Common Pitfalls §1](common_pitfalls.md#1-protobuf-7x--fielddescriptorlabel-not-available-as-instance-attribute)
is specific to the Python `protobuf 7.x` C extension backend. The Java protobuf library
exposes `FieldDescriptor.getLabel()` as a stable method call — this bug does not occur
in Java.

---

## 8. Build and Dependency Setup (Java)

```xml
<!-- Maven dependencies -->
<dependency>
  <groupId>org.apache.parquet</groupId>
  <artifactId>parquet-protobuf</artifactId>
  <version>1.14.x</version>
</dependency>
<dependency>
  <groupId>com.google.protobuf</groupId>
  <artifactId>protobuf-java</artifactId>
  <version>4.x</version>
</dependency>
```

Minimum working writer pattern:

```java
ProtoWriteSupport.setWriteSpecsCompliant(true);  // REQUIRED

try (ParquetWriter<MyMessage> writer = ProtoParquetWriter
        .<MyMessage>builder(outputPath)
        .withMessage(MyMessage.class)
        .withCompressionCodec(CompressionCodecName.SNAPPY)
        .build()) {

    for (MyMessage msg : messages) {
        writer.write(msg);
    }
}
```

---

## 9. Verdict

The Python/PyArrow stack is simpler for this specific conversion:

- No spec-compliance flag required for `LIST`/`MAP`.
- No dependency on a descriptor registry for schema inference.
- The `_upb` pitfall aside, the Python proto library behaves predictably.

Java is preferable when:

- The pipeline is part of a larger JVM ecosystem (Spark, Flink, Hadoop).
- `parquet-mr` is already a transitive dependency.
- Proto descriptors are managed centrally (e.g. via a schema registry with Java clients).

In either case, the type-compatibility constraints are identical — the format does not
change based on the writer language.
