# Results and Analysis

## Pipeline Execution Summary

All 8 datasets passed the full end-to-end pipeline (schema inference → PB3→Parquet conversion → field-by-field validation).

| Dataset | Schema Inference | PB3→Parquet | Validation | Overall |
|---|:---:|:---:|:---:|:---:|
| `basic_types` | ✓ | ✓ | ✓ | **PASS** |
| `nested_messages` | ✓ | ✓ | ✓ | **PASS** |
| `repeated_fields` | ✓ | ✓ | ✓ | **PASS** |
| `maps` | ✓ | ✓ | ✓ | **PASS** |
| `enums` | ✓ | ✓ | ✓ | **PASS** |
| `oneof` | ✓ | ✓ | ✓ | **PASS** |
| `optional_fields` | ✓ | ✓ | ✓ | **PASS** |
| `complex_nested` | ✓ | ✓ | ✓ | **PASS** |

**8/8 datasets passed (100%).**

---

## Bugs Found and Fixed

Several bugs were uncovered during the initial pipeline run where all 8 conversions failed. The root causes spanned three source files.

### 1. `src/converter.py` — `_is_repeated_field` returned False for repeated message fields

**Root cause:** The `protobuf==7.x` package uses a C extension (`_upb`) backend whose `FieldDescriptor` instances do not expose `.label` as an instance attribute. The original code called `field.label == field.LABEL_REPEATED`, which silently evaluated to `False` for every field, causing repeated message fields (e.g. `repeated Item items`) to fall into the singular-message branch. `HasField` then raised `ValueError` for a repeated field, and the except clause incorrectly called `_message_to_dict` on the `RepeatedCompositeContainer` itself, producing:

```
AttributeError: 'google._upb._message.RepeatedCompositeContainer' object has no attribute 'DESCRIPTOR'
```

**Fix:** Use `FieldDescriptor.LABEL_REPEATED` from the class import rather than via instance attribute access, with a type-name fallback. Also explicitly exclude map fields (which are also `LABEL_REPEATED` internally) so they continue to be handled by the existing map branch.

---

### 2. `src/schema_inference.py` — three bugs in `_parse_messages`

#### 2a. Regex could not handle more than one level of brace nesting

The message-matching regex `r'message\s+(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'` only handled one level of nested braces. The outermost message in `complex_nested.proto` (`ComplexNested`) contains `Person`, which in turn contains `ContactInfo` — two levels deep. The regex failed to capture `ComplexNested` at all, so `_find_main_message` returned `Person` instead, producing a completely wrong schema.

**Fix:** Replaced the regex with a bracket-counting loop that correctly finds the matching closing brace at any depth.

#### 2b. Field parsing included fields from nested `message { }` blocks

Because the field regex was applied to the full message body (including nested message definitions), fields from inner messages appeared in the outer message's schema as spurious top-level columns. For example, `RepeatedFields` incorrectly picked up `name` and `price` from its nested `Item` message.

**Fix:** Added `_strip_nested_message_blocks` to remove nested message definitions from a body before field parsing.

#### 2c. Map fields were not parsed

The field regex `r'(optional|repeated|map)?\s*(\w+)\s+(\w+)\s*=\s*\d+;'` does not match `map<K, V> name = N;` syntax. As a result, all map fields were silently dropped from inferred schemas.

**Fix:** Added a separate regex pass for map fields: `r'map<(\w+),\s*(\w+)>\s+(\w+)\s*=\s*\d+;'`.

**Also fixed:** `_resolve_type` now walks ancestor name prefixes when resolving a message type used inside a nested message (e.g. `Person` referenced inside `ComplexNested.Department` resolves to `ComplexNested.Person`).

---

### 3. `src/validator.py` — three bugs

#### 3a. PB3 file read using `split(b'\n')` instead of varint length-delimited format

The generator writes `.pb3` files in the standard length-delimited format (varint prefix + serialized message bytes). The validator read the entire file and split on `\n`, producing garbage byte chunks and:

```
Error parsing message with type '...': Wire format was corrupt
```

**Fix:** Replaced the read logic with the same varint-reading loop used by the converter.

#### 3b. `field.label == field.LABEL_REPEATED` same `_upb` bug as in the converter

**Fix:** Used type-name inspection of the field value (`'Repeated' in type(value).__name__`) as the detection strategy, with explicit map-field detection via `field.message_type.GetOptions().map_entry` taking priority.

#### 3c. Pandas returns numpy arrays and map-as-list for Parquet compound types

When a Parquet file is read back via pandas:
- `LIST` columns are returned as numpy arrays, not Python lists — causing `isinstance(pq_value, list)` checks to fail and `pd.isna(numpy_array)` to raise "truth value of array is ambiguous".
- `MAP` columns are returned as lists of `(key, value)` tuples, not dicts — causing `isinstance(pq_value, dict)` checks to fail.
- Map fields with message values (`map<string, Value>`) were not recursively converted; `dict(value)` returned raw protobuf message objects as values.

**Fix:** Added `_normalize_parquet_record` / `_normalize_value` to recursively convert numpy arrays to lists and numpy scalars to Python types before comparison. Added `_is_na` to safely handle `pd.isna` for array-like values. In `_compare_records`, Parquet list-of-tuples map representations are converted to dicts before comparison. In `_message_to_dict`, map values are recursively converted when they are protobuf messages.

---

## Protobuf → Parquet Semantic Mapping

### What maps cleanly

| Protobuf type | Parquet / PyArrow type | Round-trips correctly? |
|---|---|:---:|
| `int32`, `sint32`, `sfixed32` | `int32` | ✓ |
| `int64`, `sint64`, `sfixed64` | `int64` | ✓ |
| `uint32`, `fixed32` | `uint32` | ✓ |
| `uint64`, `fixed64` | `uint64` | ✓ |
| `float` | `float32` | ✓ |
| `double` | `float64` | ✓ |
| `bool` | `bool_` | ✓ |
| `string` | `string` (UTF-8) | ✓ |
| `bytes` | `binary` (`BYTE_ARRAY`) | ✓ |
| `optional T` (proto3 explicit presence) | nullable column | ✓ |
| `repeated T` | `LIST<T>` | ✓ |
| `map<K, V>` | `MAP<K, V>` | ✓ (order-insensitive) |
| nested `message` | `STRUCT` | ✓ |
| `enum` values | `int32` | ✓ (integer values preserved) |

### Semantic mismatches — information is lost but tests still pass

These cases convert and validate successfully because the validator only checks field *values*, not structural constraints. However, a consumer of the Parquet data loses information that was present in the original protobuf.

#### `oneof` — mutual exclusivity is not expressed

Parquet has no native concept for a union type or discriminated variant. All members of a `oneof` group are stored as independent nullable columns. The constraint that *exactly one* field is set is permanently lost:

```proto
// Proto: only one of these three can be set
oneof value {
  string text_data   = 2;
  int32  numeric_data = 3;
  bool   flag_data   = 4;
}
```

```
# Parquet row when text_data = "hello" (numeric_data and flag_data are "not set"):
text_data="hello"  numeric_data=0  flag_data=false
```

A Parquet reader cannot distinguish `numeric_data = 0` (unset, defaulting to 0) from `numeric_data = 0` (explicitly set to 0). The `WhichOneof()` information is fully lost. To preserve it, an extra discriminator column (e.g. `value_case: string`) would need to be added to the schema.

#### `enum` — symbolic names are dropped

Enum values are stored as their integer representation. The mapping from integer to name (e.g. `2 → APPROVED`) is in the `.proto` file but not in the Parquet schema or file metadata. A Parquet reader sees only numbers.

#### Proto3 scalar field presence — shared limitation, not a regression

In proto3, unset scalar fields are indistinguishable from fields explicitly set to their zero value (`0`, `""`, `false`). Parquet has the same limitation for non-nullable columns. This is a proto3 design choice rather than a proto→Parquet mismatch, and the behaviour is consistent across both representations.

#### Wire encoding variants — collapsed to logical type

`sint32`, `fixed32`, and `sfixed32` all encode as `int32` in Parquet (same for their 64-bit counterparts). The specific protobuf wire encoding (zigzag, fixed-width, etc.) is lost, though the logical integer value is preserved.

#### Map key ordering — non-deterministic

Protobuf maps have no defined iteration order. Parquet `MAP` also does not guarantee order. Downstream readers that depend on insertion order may see different orderings across serialisation/deserialisation cycles.
