"""
Parquet schema inference from Protocol Buffer .proto files.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
import pyarrow as pa


class SchemaInferenceError(Exception):
    """Raised when schema inference fails."""
    pass


class ProtoToParquetSchemaInference:
    """Infer Parquet schema from Protobuf .proto files."""
    
    # Mapping from proto types to PyArrow types
    TYPE_MAPPING = {
        'int32': pa.int32(),
        'int64': pa.int64(),
        'uint32': pa.uint32(),
        'uint64': pa.uint64(),
        'sint32': pa.int32(),
        'sint64': pa.int64(),
        'fixed32': pa.uint32(),
        'fixed64': pa.uint64(),
        'sfixed32': pa.int32(),
        'sfixed64': pa.int64(),
        'float': pa.float32(),
        'double': pa.float64(),
        'bool': pa.bool_(),
        'string': pa.string(),
        'bytes': pa.binary(),
    }
    
    def __init__(self):
        self.messages: Dict[str, List[Tuple[str, str, bool, bool]]] = {}
        self.enums: Dict[str, List[str]] = {}
        self.errors: List[str] = []
    
    def infer_schema(self, proto_file: Path) -> Optional[pa.Schema]:
        """
        Infer Parquet schema from a .proto file.
        Returns None if inference fails, with errors stored in self.errors.
        """
        self.errors = []
        self.messages = {}
        self.enums = {}
        
        try:
            proto_content = proto_file.read_text()
            self._parse_proto(proto_content)
            
            # Find the main message (typically the outermost one)
            main_message = self._find_main_message()
            if not main_message:
                self.errors.append("No message definition found in proto file")
                return None
            
            # Build schema
            schema = self._build_schema(main_message)
            return schema
            
        except Exception as e:
            self.errors.append(f"Schema inference failed: {str(e)}")
            return None
    
    def _parse_proto(self, content: str) -> None:
        """Parse proto file and extract message and enum definitions."""
        # Remove comments
        content = re.sub(r'//.*?\n', '\n', content)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Extract enums
        enum_pattern = r'enum\s+(\w+)\s*\{([^}]+)\}'
        for match in re.finditer(enum_pattern, content):
            enum_name = match.group(1)
            enum_body = match.group(2)
            values = re.findall(r'(\w+)\s*=\s*\d+', enum_body)
            self.enums[enum_name] = values
        
        # Extract messages (including nested)
        self._parse_messages(content)
    
    def _parse_messages(self, content: str, parent_prefix: str = "") -> None:
        """Recursively parse message definitions using bracket counting."""
        pos = 0
        while pos < len(content):
            match = re.search(r'\bmessage\s+(\w+)\s*\{', content[pos:])
            if not match:
                break

            message_name = match.group(1)
            body_start = pos + match.end()  # position of first char inside '{'

            # Find matching closing brace using bracket counting
            depth = 1
            i = body_start
            while i < len(content) and depth > 0:
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                i += 1

            if depth != 0:
                # Unmatched braces — skip
                pos += match.end()
                continue

            message_body = content[body_start:i - 1]
            full_name = f"{parent_prefix}{message_name}"

            # Recurse into nested messages first
            self._parse_messages(message_body, f"{full_name}.")

            # Strip nested message blocks so their fields don't pollute this message
            body_for_fields = self._strip_nested_message_blocks(message_body)

            # Parse regular (non-map) fields
            fields = []
            field_pattern = r'(optional|repeated)?\s*(\w+)\s+(\w+)\s*=\s*\d+;'
            for field_match in re.finditer(field_pattern, body_for_fields):
                modifier = field_match.group(1) or ""
                field_type = field_match.group(2)
                field_name = field_match.group(3)
                is_repeated = modifier == "repeated"
                is_optional = modifier == "optional"
                fields.append((field_name, field_type, is_repeated, is_optional))

            # Parse map fields separately (map<K,V> name = N;)
            map_field_pattern = r'map<(\w+),\s*(\w+)>\s+(\w+)\s*=\s*\d+;'
            for map_match in re.finditer(map_field_pattern, body_for_fields):
                key_type = map_match.group(1)
                value_type = map_match.group(2)
                field_name = map_match.group(3)
                field_type = f"map<{key_type},{value_type}>"
                fields.append((field_name, field_type, False, False))

            self.messages[full_name] = fields

            # Advance past this message block
            pos = i

    def _strip_nested_message_blocks(self, content: str) -> str:
        """Remove nested message definitions from content using bracket counting."""
        result = []
        pos = 0
        while pos < len(content):
            match = re.search(r'\bmessage\s+\w+\s*\{', content[pos:])
            if not match:
                result.append(content[pos:])
                break
            result.append(content[pos:pos + match.start()])
            body_start = pos + match.end()
            depth = 1
            i = body_start
            while i < len(content) and depth > 0:
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                i += 1
            pos = i
        return ''.join(result)
    
    def _find_main_message(self) -> Optional[str]:
        """Find the main (outermost) message to use as schema root."""
        # Return the first message without a dot (not nested)
        for msg_name in self.messages.keys():
            if '.' not in msg_name:
                return msg_name
        return None
    
    def _build_schema(self, message_name: str) -> pa.Schema:
        """Build PyArrow schema from a message definition."""
        if message_name not in self.messages:
            raise SchemaInferenceError(f"Message '{message_name}' not found")
        
        fields = []
        for field_name, field_type, is_repeated, is_optional in self.messages[message_name]:
            try:
                pa_field = self._convert_field(
                    field_name, field_type, is_repeated, is_optional, message_name
                )
                fields.append(pa_field)
            except Exception as e:
                self.errors.append(
                    f"Failed to convert field '{field_name}' of type '{field_type}': {str(e)}"
                )
                # Use string as fallback
                fields.append(pa.field(field_name, pa.string(), nullable=True))
        
        return pa.schema(fields)
    
    def _convert_field(
        self, 
        field_name: str, 
        field_type: str, 
        is_repeated: bool,
        is_optional: bool,
        parent_message: str
    ) -> pa.Field:
        """Convert a proto field to a PyArrow field."""
        
        # Handle map types
        if field_type.startswith('map<'):
            map_match = re.match(r'map<(\w+),\s*(\w+)>', field_type)
            if map_match:
                key_type = map_match.group(1)
                value_type = map_match.group(2)
                
                # Parquet represents maps as list of structs with key/value
                key_pa_type = self._get_primitive_type(key_type)
                value_pa_type = self._resolve_type(value_type, parent_message)
                
                map_type = pa.map_(key_pa_type, value_pa_type)
                return pa.field(field_name, map_type, nullable=True)
        
        # Get base type
        pa_type = self._resolve_type(field_type, parent_message)
        
        # Handle repeated fields (arrays)
        if is_repeated:
            pa_type = pa.list_(pa_type)
        
        # In proto3, all fields are optional by default unless repeated
        nullable = True
        
        return pa.field(field_name, pa_type, nullable=nullable)
    
    def _resolve_type(self, field_type: str, parent_message: str) -> pa.DataType:
        """Resolve a field type to PyArrow type."""
        
        # Check if it's a primitive type
        if field_type in self.TYPE_MAPPING:
            return self.TYPE_MAPPING[field_type]
        
        # Check if it's an enum
        if field_type in self.enums:
            # Represent enums as int32 (their underlying type)
            return pa.int32()
        
        # Check if it's a nested message
        # Try with parent prefix first, then ancestor prefixes
        parts = parent_message.split('.')
        while parts:
            prefix = '.'.join(parts)
            candidate = f"{prefix}.{field_type}"
            if candidate in self.messages:
                return self._build_struct_type(candidate)
            parts.pop()

        # Try without any prefix (truly top-level message)
        if field_type in self.messages:
            return self._build_struct_type(field_type)

        # Unknown type - use string as fallback
        self.errors.append(f"Unknown type '{field_type}', using string as fallback")
        return pa.string()
    
    def _get_primitive_type(self, type_name: str) -> pa.DataType:
        """Get primitive PyArrow type."""
        if type_name in self.TYPE_MAPPING:
            return self.TYPE_MAPPING[type_name]
        raise SchemaInferenceError(f"Unknown primitive type: {type_name}")
    
    def _build_struct_type(self, message_name: str) -> pa.StructType:
        """Build a struct type from a message definition."""
        if message_name not in self.messages:
            raise SchemaInferenceError(f"Message '{message_name}' not found")
        
        struct_fields = []
        for field_name, field_type, is_repeated, is_optional in self.messages[message_name]:
            pa_field = self._convert_field(
                field_name, field_type, is_repeated, is_optional, message_name
            )
            struct_fields.append(pa_field)
        
        return pa.struct(struct_fields)
    
    def get_error_summary(self) -> str:
        """Get a summary of all errors encountered during inference."""
        if not self.errors:
            return "No errors"
        return "\n".join(f"- {error}" for error in self.errors)
