# Common Pitfalls and Conversion Bugs

This document records bugs encountered when building a PB3→Parquet conversion pipeline
in Python, along with their root causes and fixes. Each pitfall is general — it will
hit any project doing this conversion, not just this one.

**Related reading:**
- [Data Format Compatibility Analysis](compatibility_analysis.md) — type-level compatibility and recommendations
- [Codebase Guide](codebase.md) — how the pipeline is implemented
- [Pipeline Results](results.md) — empirical pass/fail results across 8 datasets

---

## 1. `protobuf 7.x` — `FieldDescriptor.label` not available as instance attribute

**Affects:** Any code that reads `field.label` on a `FieldDescriptor` instance.  
**Source file in this project:** `src/converter.py`, `src/validator.py`

**Root cause:** The `protobuf 7.x` package uses a C extension (`_upb`) backend. Unlike
earlier versions, `FieldDescriptor` instances from the `_upb` backend do not expose
`.label` as a Python instance attribute. Code that called
`field.label == field.LABEL_REPEATED` silently evaluated to `False` for every field,
causing repeated message fields to fall into the singular-message branch. `HasField`
then raised `ValueError` for a repeated field, and the except clause incorrectly called
`_message_to_dict` on the `RepeatedCompositeContainer` itself:

```
AttributeError: 'google._upb._message.RepeatedCompositeContainer' object has no attribute 'DESCRIPTOR'
```

**Fix:** Import `FieldDescriptor` from the class and use the class constant directly,
with a type-name fallback for safety:

```python
from google.protobuf.descriptor import FieldDescriptor

try:
    is_repeated = field.label == FieldDescriptor.LABEL_REPEATED
except AttributeError:
    # _upb backend fallback
    is_repeated = 'Repeated' in type(value).__name__
```

Also explicitly exclude map fields (which are internally `LABEL_REPEATED`) so they
continue to be handled by the map branch rather than the repeated branch.

---

## 2. `src/schema_inference.py` — three bugs in `.proto` parsing

### 2a. Regex-based parsing fails beyond one level of brace nesting

**Root cause:** The message-matching regex
`r'message\s+(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'`
only handles one level of nested braces. A message like `ComplexNested` that contains
`Person`, which in turn contains `ContactInfo`, is two levels deep. The regex silently
fails to capture the outermost message, so `_find_main_message` returns the wrong
(inner) message and produces a completely wrong schema.

**Fix:** Replace the regex with a bracket-counting loop that finds the matching closing
brace at any depth:

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

### 2b. Field regex picks up fields from nested `message { }` blocks

**Root cause:** When the field regex is applied to the full message body (including
nested message definitions), fields from inner messages appear as spurious top-level
columns. For example, `RepeatedFields` incorrectly picked up `name` and `price` from
its nested `Item` message.

**Fix:** Strip nested message blocks from the body *before* running the field regex:

```python
def _strip_nested_message_blocks(content: str) -> str:
    """Remove nested message { ... } definitions using bracket counting."""
    ...
```

### 2c. `map<K, V>` fields are silently dropped

**Root cause:** The field regex
`r'(optional|repeated|map)?\s*(\w+)\s+(\w+)\s*=\s*\d+;'`
does not match `map<K, V> name = N;` syntax — the angle-bracket generic form is not
captured. All map fields are silently omitted from the inferred schema.

**Fix:** Add a separate regex pass specifically for map fields:

```python
map_field_pattern = r'map<(\w+),\s*(\w+)>\s+(\w+)\s*=\s*\d+;'
for match in re.finditer(map_field_pattern, body_for_fields):
    key_type, value_type, field_name = match.group(1), match.group(2), match.group(3)
```

**Also fixed in this area:** `_resolve_type` must walk ancestor name prefixes when
resolving a message type used inside a nested message. `Person` referenced inside
`ComplexNested.Department` resolves to `ComplexNested.Person`, not a top-level
`Person`.

---

## 3. `src/validator.py` — three bugs

### 3a. Reading length-delimited `.pb3` files with `split(b'\n')`

**Root cause:** The standard protobuf multi-message file format prefixes each record
with a varint-encoded byte count. Reading the file and splitting on `\n` produces
garbage byte chunks and corrupt parse errors:

```
Error parsing message with type '...': Wire format was corrupt
```

**Fix:** Read the file with a varint loop:

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

### 3b. Same `protobuf 7.x _upb` bug in the validator

The same `field.label` instance-attribute issue from pitfall 1 also appeared in the
validator's `_message_to_dict`. Fix is the same: use type-name inspection
(`'Repeated' in type(value).__name__`) with map-field detection taking priority.

### 3c. pandas returns non-native types for Parquet compound columns

**Root cause:** When a Parquet file is read back via `read_table().to_pandas()`:

| Parquet type | What pandas returns | What broke |
|---|---|---|
| `LIST` column | `numpy.ndarray` | `isinstance(v, list)` → `False`; `pd.isna(array)` → "truth value of array is ambiguous" |
| `MAP` column | `list` of `(key, value)` tuples | `isinstance(v, dict)` → `False` |
| `MAP` with message values | tuple values are raw protobuf objects | `dict(value)` returns unreadable objects |

**Fix:**

1. `_normalize_parquet_record` / `_normalize_value` — recursively convert
   `numpy.ndarray` → `list`, `numpy.integer` → `int`, `numpy.floating` → `float`,
   `numpy.bool_` → `bool` before any comparison.
2. `_is_na` — wrap `pd.isna` in a try/except to safely handle array-like values.
3. In `_compare_records` — convert Parquet list-of-tuples map representations to
   `dict` before comparing with the proto dict.
4. In `_message_to_dict` — recursively convert map values that are protobuf message
   objects before storing them.
