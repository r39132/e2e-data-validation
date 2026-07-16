# Java Considerations for PB3 → Parquet Conversion

This document explains how a Java implementation of the same PB3→Parquet pipeline
would differ from the Python/PyArrow implementation documented in this project,
targeting **Java 17 LTS** as the minimum and noting Java 21 LTS improvements where
applicable.

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

## 1. Recommended Library Versions

| Library | Artifact | Recommended version | Notes |
|---|---|---|---|
| Parquet (proto support) | `org.apache.parquet:parquet-protobuf` | **1.17.1** | Latest stable; includes spec-compliant LIST/MAP encoding |
| Parquet core | `org.apache.parquet:parquet-hadoop` | **1.17.1** | Match `parquet-protobuf` version |
| Protobuf Java | `com.google.protobuf:protobuf-java` | **4.35.0** | Java equivalent of Python `protobuf 7.x`; same `_upb` generation but stable API |
| Hadoop (for local FS) | `org.apache.hadoop:hadoop-common` | **3.4.x** | Required by parquet-hadoop; use `LocalFileSystem` for non-HDFS |

### Maven BOM / `pom.xml`

```xml
<properties>
  <java.version>17</java.version>
  <parquet.version>1.17.1</parquet.version>
  <protobuf.version>4.35.0</protobuf.version>
  <hadoop.version>3.4.1</hadoop.version>
</properties>

<dependencies>
  <dependency>
    <groupId>org.apache.parquet</groupId>
    <artifactId>parquet-protobuf</artifactId>
    <version>${parquet.version}</version>
  </dependency>
  <dependency>
    <groupId>org.apache.parquet</groupId>
    <artifactId>parquet-hadoop</artifactId>
    <version>${parquet.version}</version>
  </dependency>
  <dependency>
    <groupId>com.google.protobuf</groupId>
    <artifactId>protobuf-java</artifactId>
    <version>${protobuf.version}</version>
  </dependency>
  <dependency>
    <groupId>org.apache.hadoop</groupId>
    <artifactId>hadoop-common</artifactId>
    <version>${hadoop.version}</version>
    <!-- Exclude logging to avoid SLF4J conflicts -->
    <exclusions>
      <exclusion>
        <groupId>org.slf4j</groupId>
        <artifactId>slf4j-reload4j</artifactId>
      </exclusion>
    </exclusions>
  </dependency>
</dependencies>

<build>
  <plugins>
    <plugin>
      <groupId>com.github.os72</groupId>
      <artifactId>protoc-jar-maven-plugin</artifactId>
      <version>3.11.4</version>
      <executions>
        <execution>
          <goals><goal>run</goal></goals>
          <configuration>
            <protocVersion>${protobuf.version}</protocVersion>
            <inputDirectories><include>src/main/proto</include></inputDirectories>
          </configuration>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```

---

## 2. `repeated` and `map` — the Biggest Java-Specific Risk

This is where Java diverges most significantly from PyArrow.

`parquet-java` (`parquet-mr`) has **two LIST/MAP encoding modes**:

| Mode | How to enable | Parquet spec compliant? | PyArrow readable? |
|---|---|---|---|
| Legacy (older default) | Default in versions < 1.12 | ❌ No | ⚠️ Sometimes |
| Spec-compliant | `ProtoWriteSupport.setWriteSpecsCompliant(true)` | ✅ Yes | ✅ Yes |

As of parquet-protobuf **1.13+**, spec-compliant mode is the default, but **the call
is still required** when writing to ensure it is not disabled by a configuration
override in the Hadoop environment:

```java
// ALWAYS call this — do not rely on the default
ProtoWriteSupport.setWriteSpecsCompliant(true);
```

PyArrow always writes spec-compliant encoding. A file written by Java in legacy mode
may produce read errors or silently wrong data when consumed by PyArrow, Arrow Flight,
or DuckDB. This was the "conditional hedge" in the original analytical design document
that the Python empirical results did not need.

---

## 3. Schema Inference

| | Python (this project) | Java |
|---|---|---|
| Approach | Custom bracket-counting `.proto` parser (`schema_inference.py`) | `ProtoSchemaConverter` reads the proto descriptor at runtime |
| Integer widths | Exact widths preserved | Exact widths preserved when using `ProtoParquetWriter` with a descriptor |
| Risk of upcasting | Low — schema from `.proto` spec | Present if falling back to Avro/generic inference from data |
| Nested message resolution | Manual prefix-walking in `_resolve_type` | Handled automatically by the descriptor API |

**Best practice:** Always use `ProtoParquetWriter` with a typed message class —
never infer schema from data values. Inferring from data can silently upcast
`int32 → int64`.

---

## 4. Minimum Working Writer Pattern (Java 17+)

```java
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.parquet.hadoop.ParquetWriter;
import org.apache.parquet.hadoop.metadata.CompressionCodecName;
import org.apache.parquet.proto.ProtoParquetWriter;
import org.apache.parquet.proto.ProtoWriteSupport;

public class Pb3ToParquetConverter {

    public static <T extends com.google.protobuf.Message> void convert(
            Iterable<T> messages,
            Class<T> messageClass,
            Path outputPath) throws Exception {

        // REQUIRED: ensure spec-compliant LIST/MAP encoding
        ProtoWriteSupport.setWriteSpecsCompliant(true);

        var conf = new Configuration();

        try (ParquetWriter<T> writer = ProtoParquetWriter.<T>builder(outputPath)
                .withMessage(messageClass)
                .withConf(conf)
                .withCompressionCodec(CompressionCodecName.SNAPPY)
                .withRowGroupSize(128 * 1024 * 1024L)  // 128 MB
                .withPageSize(1024 * 1024)              // 1 MB
                .build()) {

            for (T msg : messages) {
                writer.write(msg);
            }
        }
    }
}
```

### Reading length-delimited `.pb3` files

Use the protobuf-provided API — do not implement a varint loop manually:

```java
import com.google.protobuf.CodedInputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

public static <T extends com.google.protobuf.Message> List<T> readPb3(
        InputStream in,
        com.google.protobuf.Parser<T> parser) throws Exception {

    var records = new ArrayList<T>();
    T msg;
    // readDelimitedFrom handles the varint length prefix correctly
    while ((msg = parser.parseDelimitedFrom(in)) != null) {
        records.add(msg);
    }
    return records;
}
```

This is the Java equivalent of the custom `_read_varint` loop in
[`src/converter.py`](../src/converter.py) — the protobuf library handles the
length-delimited framing so you don't have to.

---

## 5. Scalability: Generic vs Per-Dataset Code

> **Critical architectural constraint:** A production pipeline must convert *any*
> proto3 dataset to Parquet without writing custom code per schema. Any approach
> that requires per-message Java classes, custom sealed interfaces, or hand-written
> field mappings does not scale beyond a handful of datasets and is a non-starter
> for a library that must handle tens of thousands of schemas.

The Python pipeline in this project already satisfies this constraint:
`schema_inference.py` and `converter.py` use proto reflection
(`message.DESCRIPTOR.fields`) to process any message type at runtime — no per-dataset
code exists or is needed.

The Java equivalent requires the same approach: **`DynamicMessage` + runtime
`Descriptor` loading**.

### Java: Generic Converter Using `DynamicMessage`

Instead of generating a typed Java class per proto message, load the descriptor at
runtime and use `DynamicMessage` to process any schema:

```java
import com.google.protobuf.DescriptorProtos.FileDescriptorSet;
import com.google.protobuf.Descriptors.Descriptor;
import com.google.protobuf.Descriptors.FileDescriptor;
import com.google.protobuf.DynamicMessage;
import org.apache.parquet.proto.ProtoParquetWriter;
import org.apache.parquet.proto.ProtoWriteSupport;

public class GenericPb3ToParquetConverter {

    /**
     * Convert any .pb3 file to Parquet without generated code.
     *
     * @param descriptorSet  compiled FileDescriptorSet from `protoc --descriptor_set_out`
     * @param messageType    message name, e.g. "BasicTypes"
     * @param pb3Stream      length-delimited .pb3 input
     * @param outputPath     Parquet output path
     */
    public static void convert(
            FileDescriptorSet descriptorSet,
            String messageType,
            InputStream pb3Stream,
            Path outputPath) throws Exception {

        Descriptor descriptor = resolveDescriptor(descriptorSet, messageType);

        ProtoWriteSupport.setWriteSpecsCompliant(true);

        try (var writer = ProtoParquetWriter.builder(outputPath)
                .withDescriptor(descriptor)        // schema from descriptor, not class
                .withCompressionCodec(CompressionCodecName.SNAPPY)
                .withRowGroupSize(128 * 1024 * 1024L)
                .build()) {

            DynamicMessage msg;
            while ((msg = DynamicMessage.parseDelimitedFrom(descriptor, pb3Stream)) != null) {
                writer.write(msg);
            }
        }
    }

    private static Descriptor resolveDescriptor(
            FileDescriptorSet fds, String messageType) throws Exception {
        var fileDescriptors = new HashMap<String, FileDescriptor>();
        for (var fdProto : fds.getFileList()) {
            var deps = fdProto.getDependencyList().stream()
                    .map(fileDescriptors::get)
                    .toArray(FileDescriptor[]::new);
            var fd = FileDescriptor.buildFrom(fdProto, deps);
            fileDescriptors.put(fdProto.getName(), fd);
            var descriptor = fd.findMessageTypeByName(messageType);
            if (descriptor != null) return descriptor;
        }
        throw new IllegalArgumentException("Message type not found: " + messageType);
    }
}
```

### Compiling a `FileDescriptorSet` at Build Time

The `FileDescriptorSet` is a binary file produced once during the build — not once
per dataset:

```bash
# Compile ALL .proto files into a single binary descriptor set
protoc \
  --descriptor_set_out=schema.pb \
  --include_imports \
  --proto_path=src/main/proto \
  $(find src/main/proto -name "*.proto")
```

At runtime, load it once and convert any message type by name:

```java
var fds = FileDescriptorSet.parseFrom(Files.readAllBytes(Path.of("schema.pb")));

// Same binary handles any number of schemas — no per-schema code
new GenericPb3ToParquetConverter().convert(fds, "BasicTypes",   in1, out1);
new GenericPb3ToParquetConverter().convert(fds, "ComplexNested", in2, out2);
new GenericPb3ToParquetConverter().convert(fds, "Maps",          in3, out3);
```

### At Scale: Schema Registry Integration

For tens of thousands of schemas, fetch descriptors from a registry at job start
rather than bundling a compiled binary with the pipeline:

| Registry | How to get the `Descriptor` |
|---|---|
| Confluent Schema Registry | `SchemaRegistryClient.getBySubjectAndId()` → parse `FileDescriptorProto` |
| Buf Schema Registry | `buf export` → `FileDescriptorSet` binary |
| Custom file store | Load `.pb` binary from S3/GCS/HDFS at job start |

### Generic enum → string conversion (no hardcoded switch)

In a generic pipeline, use the descriptor to look up enum names — never hardcode
values:

```java
// Works for any enum type, any number of values, any schema
FieldDescriptor field = descriptor.findFieldByName("status");
int enumValue = (int) dynamicMessage.getField(field);
String enumName = field.getEnumType().findValueByNumber(enumValue).getName();
// Returns "APPROVED" for value 2 — driven entirely by the descriptor
```

### Generic `oneof` discriminator column

Detect `oneof` fields via the descriptor and emit discriminator columns
automatically — no custom code per message:

```java
// Emit a "<group>_case" column for every oneof group in the message
for (var oneof : descriptor.getRealOneofs()) {
    String activeField = oneof.getFields().stream()
            .filter(dynamicMessage::hasField)
            .map(FieldDescriptor::getName)
            .findFirst()
            .orElse(null);
    row.put(oneof.getName() + "_case", activeField);
}
```

---

## 6. Java 17+ Language Features — Application Layer Only

> **Scope:** The features below apply to application code built *on top of* the
> generic pipeline (section 5), not to the pipeline itself. They require generating
> typed Java classes from `.proto` files and are only appropriate for a small, fixed
> set of well-known message types in an application — not for a generic converter.

### Records for immutable result types

```java
public record ValidationResult(boolean success, String message, List<String> details) {
    public static ValidationResult pass(String message) {
        return new ValidationResult(true, message, List.of());
    }
    public static ValidationResult fail(String message, List<String> details) {
        return new ValidationResult(false, message, details);
    }
}
```

### Sealed interfaces to model `oneof` — does not scale, application layer only

The sealed interface pattern gives compile-time enforcement of `oneof` semantics but
**requires one interface per proto message with a `oneof` field**. It is only
appropriate for a small, fixed set of known message types — not for a generic pipeline:

```java
// NOT for a generic pipeline — only viable for a handful of known message types
public sealed interface Payload
        permits Payload.TextData, Payload.NumericData, Payload.FlagData {
    record TextData(String value)   implements Payload {}
    record NumericData(int value)   implements Payload {}
    record FlagData(boolean value)  implements Payload {}
}
```

At scale, use the generic descriptor-based `oneof` detection shown in section 5
instead.

### `var` for complex generic types

```java
var writer = ProtoParquetWriter.<MyMessage>builder(outputPath)
        .withMessage(MyMessage.class)
        .build();
```

### Text blocks for inline `.proto` in tests

```java
String protoSchema = """
    syntax = "proto3";
    message BasicTypes {
      int32 int32_field = 1;
      string string_field = 2;
    }
    """;
```

---

## 7. Reading Parquet Back in Java

When reading Parquet files back in Java:

| Column type | Java / `parquet-proto` returns | Equivalent Python issue |
|---|---|---|
| `LIST` | `List<T>` | numpy array (fixed by `_normalize_value` in Python) |
| `MAP` | `Map<K, V>` | list of tuples (fixed by `dict()` conversion in Python) |
| `STRUCT` | Nested proto `Message` | handled by `_message_to_dict` recursion in Python |

Java's `parquet-proto` returns proper typed collections — the numpy/tuple
normalisation issues from [Common Pitfalls §3c](common_pitfalls.md#3c-pandas-returns-non-native-types-for-parquet-compound-columns)
do not apply. However, map key ordering remains non-deterministic in both languages.

---

## 8. `oneof`, `enum`, `Any`, `Struct` — Same Semantic Losses

These are format-level constraints, not language-level:

| Type | Java behaviour | Python behaviour |
|---|---|---|
| `oneof` | Flattened to independent nullable columns | Same |
| `enum` | Stored as `INT32`; names lost | Same |
| `google.protobuf.Any` | Raw bytes; structure lost | Same |
| `google.protobuf.Struct` | No fixed schema; no clean mapping | Same |

The recommendations in [compatibility_analysis.md](compatibility_analysis.md)
(discriminator columns for `oneof`, string conversion for `enum`, avoid `Any`/`Struct`)
apply equally to Java. The sealed interface pattern in section 6 above is a Java-native
way to partially recover `oneof` semantics in the writer layer.

---

## 9. The `_upb` Bug is Python-Specific

The `FieldDescriptor.label` instance-attribute bug documented in
[Common Pitfalls §1](common_pitfalls.md#1-protobuf-7x--fielddescriptorlabel-not-available-as-instance-attribute)
is specific to the Python `protobuf 7.x` C extension backend. The Java protobuf library
exposes `FieldDescriptor.getLabel()` as a stable, typed method call — this bug does
not occur in Java.

---

## 10. Library Stack Comparison

| Layer | Python (this project) | Java equivalent |
|---|---|---|
| Schema from `.proto` | `ProtoToParquetSchemaInference` (custom) | `ProtoSchemaConverter` via `parquet-protobuf 1.17.1` |
| Write Parquet | `pyarrow.parquet.write_table` | `ProtoParquetWriter` via `parquet-protobuf 1.17.1` |
| Read Parquet | `pyarrow.parquet.read_table` | `ProtoParquetReader` via `parquet-protobuf 1.17.1` |
| Proto serialization | `protobuf 7.x` Python package | `protobuf-java 4.35.0` |
| Length-delimited stream | Custom varint loop | `parser.parseDelimitedFrom(inputStream)` |
| Validate | Custom `DataValidator` | Custom comparator; AssertJ for fluent assertions |

---

## 11. Verdict

The Python/PyArrow stack is simpler for this specific conversion:

- No spec-compliance flag required for `LIST`/`MAP`.
- No dependency on Hadoop for local file access.
- Lighter setup — no `protoc` Maven plugin needed for schema inference.
- The `_upb` pitfall aside, the Python proto library behaves predictably.

Java is preferable when:

- The pipeline runs inside a JVM ecosystem (Spark, Flink, Hadoop, Kafka Streams).
- `parquet-mr` is already a transitive dependency.
- Proto descriptors are managed centrally via a schema registry with Java clients.
- Java 17+ sealed interfaces and records provide meaningful enforcement of `oneof`
  semantics in the application layer that compensates for Parquet's lack of union types.

In either case, the type-compatibility constraints are identical — the format does not
change based on the writer language.

