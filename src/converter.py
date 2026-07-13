"""
Convert PB3 binary files to Parquet format.
"""
from pathlib import Path
from typing import Any, Dict, List
import pyarrow as pa
import pyarrow.parquet as pq
import sys


class PB3ToParquetConverter:
    """Convert Protocol Buffer binary files to Parquet format."""
    
    def __init__(self, schema: pa.Schema):
        self.schema = schema
    
    def convert(
        self, 
        pb3_file: Path, 
        parquet_file: Path,
        proto_module_path: Path,
        message_class_name: str
    ) -> bool:
        """
        Convert a .pb3 file to Parquet format.
        
        Args:
            pb3_file: Path to input .pb3 file
            parquet_file: Path to output .parquet file
            proto_module_path: Path to directory containing compiled proto Python module
            message_class_name: Name of the protobuf message class
            
        Returns:
            True if conversion successful, False otherwise
        """
        try:
            # Import the proto module
            sys.path.insert(0, str(proto_module_path))
            proto_module_name = proto_module_path.name
            pb_module = __import__(f"{proto_module_name}_pb2")
            message_class = getattr(pb_module, message_class_name)
            
            # Read PB3 file and parse messages
            records = self._read_pb3(pb3_file, message_class)
            
            # Convert to PyArrow table
            table = self._records_to_table(records)
            
            # Write Parquet file
            pq.write_table(table, parquet_file)
            
            sys.path.pop(0)
            return True
            
        except Exception as e:
            print(f"Conversion error: {e}")
            if str(proto_module_path) in sys.path:
                sys.path.remove(str(proto_module_path))
            return False
    
    def _read_pb3(self, pb3_file: Path, message_class: Any) -> List[Any]:
        """Read and parse PB3 binary file (length-delimited format)."""
        records = []
        
        with open(pb3_file, 'rb') as f:
            while True:
                # Read varint length
                length = self._read_varint(f)
                if length is None:
                    break
                    
                # Read message bytes
                msg_bytes = f.read(length)
                if len(msg_bytes) != length:
                    break
                    
                msg = message_class()
                msg.ParseFromString(msg_bytes)
                records.append(msg)
        
        return records
    
    def _read_varint(self, f) -> int:
        """Read a varint from file."""
        result = 0
        shift = 0
        
        while True:
            byte_data = f.read(1)
            if not byte_data:
                return None
                
            byte = byte_data[0]
            result |= (byte & 0x7F) << shift
            
            if not (byte & 0x80):
                return result
                
            shift += 7
    
    def _records_to_table(self, records: List[Any]) -> pa.Table:
        """Convert protobuf messages to PyArrow table."""
        # Convert each message to dictionary
        data_dicts = [self._message_to_dict(msg) for msg in records]
        
        # Create table from dictionaries
        # PyArrow will handle type conversion based on schema
        arrays = []
        for field in self.schema:
            field_name = field.name
            field_data = [record.get(field_name) for record in data_dicts]
            
            # Handle None values and create array with proper type
            array = self._create_array(field_data, field.type)
            arrays.append(array)
        
        return pa.Table.from_arrays(arrays, schema=self.schema)
    
    def _is_repeated_field(self, field, value) -> bool:
        """Check if a field is a repeated list field (not a map field)."""
        # Use FieldDescriptor class constant directly to avoid _upb instance attribute issues
        try:
            from google.protobuf.descriptor import FieldDescriptor
            if field.label != FieldDescriptor.LABEL_REPEATED:
                return False
            # Map fields are also LABEL_REPEATED internally but must be handled separately
            if field.message_type and field.message_type.GetOptions().map_entry:
                return False
            return True
        except (AttributeError, ImportError):
            pass

        # Fallback: check value type name ('Repeated' present, 'Map' absent)
        type_name = type(value).__name__
        return 'Repeated' in type_name
    
    def _message_to_dict(self, message: Any) -> Dict[str, Any]:
        """Convert a protobuf message to a dictionary."""
        result = {}
        
        for field in message.DESCRIPTOR.fields:
            value = getattr(message, field.name)
            
            # Handle different field types
            if field.message_type:
                if self._is_repeated_field(field, value):
                    # Repeated message field
                    result[field.name] = [self._message_to_dict(item) for item in value]
                elif field.message_type.GetOptions().map_entry:
                    # Map field
                    result[field.name] = self._convert_map(value)
                else:
                    # Singular message field - check if it's set
                    try:
                        if message.HasField(field.name):
                            result[field.name] = self._message_to_dict(value)
                        else:
                            result[field.name] = None
                    except ValueError:
                        # Field doesn't support HasField (shouldn't happen for singular message fields)
                        result[field.name] = self._message_to_dict(value) if value else None
            elif self._is_repeated_field(field, value):
                # Repeated scalar field
                result[field.name] = list(value)
            else:
                # Scalar field
                if field.type == field.TYPE_BYTES:
                    result[field.name] = bytes(value)
                elif field.type == field.TYPE_ENUM:
                    result[field.name] = int(value)
                else:
                    result[field.name] = value
        
        return result
    
    def _convert_map(self, map_field: Any) -> Dict[str, Any]:
        """Convert a protobuf map field to Python dict."""
        result = {}
        for key, value in map_field.items():
            # Check if value is a message
            if hasattr(value, 'DESCRIPTOR'):
                result[key] = self._message_to_dict(value)
            else:
                result[key] = value
        return result
    
    def _create_array(self, data: List[Any], pa_type: pa.DataType) -> pa.Array:
        """Create a PyArrow array with proper type handling."""
        try:
            # Handle struct types (nested messages)
            if pa.types.is_struct(pa_type):
                return self._create_struct_array(data, pa_type)
            
            # Handle list types (repeated fields)
            elif pa.types.is_list(pa_type):
                return self._create_list_array(data, pa_type)
            
            # Handle map types
            elif pa.types.is_map(pa_type):
                return self._create_map_array(data, pa_type)
            
            # Handle primitive types
            else:
                return pa.array(data, type=pa_type)
                
        except Exception as e:
            print(f"Array creation error for type {pa_type}: {e}")
            # Fallback to null array
            return pa.nulls(len(data), type=pa_type)
    
    def _create_struct_array(self, data: List[Any], pa_type: pa.StructType) -> pa.Array:
        """Create a struct array from list of dicts."""
        if not data or all(item is None for item in data):
            return pa.nulls(len(data), type=pa_type)
        
        # Build arrays for each field
        field_arrays = []
        for field in pa_type:
            field_data = [
                item.get(field.name) if item is not None else None 
                for item in data
            ]
            field_array = self._create_array(field_data, field.type)
            field_arrays.append(field_array)
        
        return pa.StructArray.from_arrays(field_arrays, fields=list(pa_type))
    
    def _create_list_array(self, data: List[Any], pa_type: pa.ListType) -> pa.Array:
        """Create a list array from list of lists."""
        # Get the value type
        value_type = pa_type.value_type
        
        # Flatten and create offsets
        values = []
        offsets = [0]
        
        for item in data:
            if item is None or not item:
                offsets.append(offsets[-1])
            else:
                values.extend(item)
                offsets.append(offsets[-1] + len(item))
        
        # Create value array
        if values:
            value_array = self._create_array(values, value_type)
        else:
            value_array = pa.array([], type=value_type)
        
        return pa.ListArray.from_arrays(pa.array(offsets), value_array)
    
    def _create_map_array(self, data: List[Any], pa_type: pa.MapType) -> pa.Array:
        """Create a map array from list of dicts."""
        # PyArrow represents maps as list of structs with 'key' and 'value' fields
        keys = []
        values = []
        offsets = [0]
        
        for item in data:
            if item is None or not item:
                offsets.append(offsets[-1])
            else:
                for k, v in item.items():
                    keys.append(k)
                    values.append(v)
                offsets.append(offsets[-1] + len(item))
        
        # Create key and value arrays
        key_array = pa.array(keys, type=pa_type.key_type)
        value_array = self._create_array(values, pa_type.item_type)
        
        return pa.MapArray.from_arrays(pa.array(offsets), key_array, value_array)
