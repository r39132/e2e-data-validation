"""
Dataset generator for comprehensive Protobuf3 type testing.
Creates .proto files, JSON data, and compiled .pb3 binary files.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List
import subprocess


class DatasetGenerator:
    """Generate test datasets covering various Protobuf3 features."""
    
    def __init__(self, output_dir: str = "datasets"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_all_datasets(self) -> List[str]:
        """Generate all test datasets and return list of dataset names."""
        datasets = [
            self._generate_basic_types(),
            self._generate_nested_messages(),
            self._generate_repeated_fields(),
            self._generate_maps(),
            self._generate_enums(),
            self._generate_oneof(),
            self._generate_optional_fields(),
            self._generate_complex_nested(),
        ]
        return datasets
    
    def _serialize_for_json(self, obj: Any) -> Any:
        """Convert bytes to hex strings for JSON serialization."""
        if isinstance(obj, bytes):
            return obj.hex()
        elif isinstance(obj, dict):
            return {k: self._serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_for_json(item) for item in obj]
        else:
            return obj
    
    def _create_dataset(
        self, 
        name: str, 
        proto_content: str, 
        data: List[Dict[str, Any]]
    ) -> str:
        """Create a complete dataset with .proto, .json, and .pb3 files."""
        dataset_path = self.output_dir / name
        dataset_path.mkdir(exist_ok=True)
        
        # Write .proto file
        proto_file = dataset_path / f"{name}.proto"
        with open(proto_file, 'w') as f:
            f.write(proto_content)
        
        # Write JSON data (convert bytes to hex for JSON)
        json_file = dataset_path / f"{name}.json"
        with open(json_file, 'w') as f:
            json_data = self._serialize_for_json(data)
            json.dump(json_data, f, indent=2)
        
        # Compile proto to Python
        self._compile_proto(dataset_path, name)
        
        # Generate .pb3 binary (use original data with bytes)
        self._generate_pb3(dataset_path, name, data)
        
        return name
    
    def _compile_proto(self, dataset_path: Path, name: str) -> None:
        """Compile .proto file to Python."""
        result = subprocess.run(
            ["protoc", f"--python_out={dataset_path}", f"{name}.proto"],
            cwd=dataset_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Proto compilation failed: {result.stderr}")
    
    def _generate_pb3(
        self, 
        dataset_path: Path, 
        name: str, 
        data: List[Dict[str, Any]]
    ) -> None:
        """Generate .pb3 binary file from JSON data."""
        # Import the compiled proto module dynamically
        import sys
        sys.path.insert(0, str(dataset_path))
        
        pb_module = __import__(f"{name}_pb2")
        message_class = getattr(pb_module, self._get_message_name(name))
        
        # Create binary file
        pb3_file = dataset_path / f"{name}.pb3"
        with open(pb3_file, 'wb') as f:
            for record in data:
                msg = message_class()
                self._populate_message(msg, record)
                serialized = msg.SerializeToString()
                # Write length-delimited format (varint length + message)
                self._write_varint(f, len(serialized))
                f.write(serialized)
        
        sys.path.pop(0)
    
    def _write_varint(self, f, value: int) -> None:
        """Write a varint (variable-length integer) to file."""
        while value > 0x7F:
            f.write(bytes([(value & 0x7F) | 0x80]))
            value >>= 7
        f.write(bytes([value & 0x7F]))
    
    def _populate_message(self, msg: Any, data: Dict[str, Any]) -> None:
        """Populate a protobuf message from dictionary data."""
        for key, value in data.items():
            if isinstance(value, dict):
                field = getattr(msg, key)
                # Check if it's a map field (has DESCRIPTOR with message_type.GetOptions().map_entry)
                # Or simpler: check if the field supports dict-like operations
                try:
                    # Try to treat it as a map field
                    field.clear()
                    for map_key, map_value in value.items():
                        if isinstance(map_value, dict):
                            # Map with message values
                            nested = field[map_key]
                            self._populate_message(nested, map_value)
                        else:
                            # Map with scalar values
                            field[map_key] = map_value
                except (AttributeError, TypeError):
                    # Not a map field, treat as nested message
                    self._populate_message(field, value)
            elif isinstance(value, list):
                field = getattr(msg, key)
                # Check if list contains messages (dicts) or scalars
                if value and isinstance(value[0], dict):
                    # Repeated message field
                    for item in value:
                        nested = field.add()
                        self._populate_message(nested, item)
                else:
                    # Repeated scalar field
                    field.extend(value)
            else:
                setattr(msg, key, value)
    
    def _get_message_name(self, dataset_name: str) -> str:
        """Convert dataset name to message class name."""
        parts = dataset_name.split('_')
        return ''.join(word.capitalize() for word in parts)
    
    # Dataset generators for different PB3 features
    
    def _generate_basic_types(self) -> str:
        """Test basic scalar types."""
        name = "basic_types"
        proto = '''syntax = "proto3";

message BasicTypes {
  int32 int32_field = 1;
  int64 int64_field = 2;
  uint32 uint32_field = 3;
  uint64 uint64_field = 4;
  float float_field = 5;
  double double_field = 6;
  bool bool_field = 7;
  string string_field = 8;
  bytes bytes_field = 9;
}
'''
        data = [
            {
                "int32_field": 42,
                "int64_field": 9223372036854775807,
                "uint32_field": 4294967295,
                "uint64_field": 18446744073709551615,
                "float_field": 3.14,
                "double_field": 2.718281828,
                "bool_field": True,
                "string_field": "Hello, Protobuf!",
                "bytes_field": b"binary data"
            },
            {
                "int32_field": -100,
                "int64_field": -1234567890,
                "uint32_field": 0,
                "uint64_field": 12345,
                "float_field": -99.9,
                "double_field": 0.0,
                "bool_field": False,
                "string_field": "Test 测试",
                "bytes_field": b"\x00\x01\x02\xff"
            }
        ]
        return self._create_dataset(name, proto, data)
    
    def _generate_nested_messages(self) -> str:
        """Test nested message types."""
        name = "nested_messages"
        proto = '''syntax = "proto3";

message NestedMessages {
  message Address {
    string street = 1;
    string city = 2;
    int32 zip_code = 3;
  }
  
  string name = 1;
  Address address = 2;
}
'''
        data = [
            {
                "name": "John Doe",
                "address": {
                    "street": "123 Main St",
                    "city": "Springfield",
                    "zip_code": 12345
                }
            }
        ]
        return self._create_dataset(name, proto, data)
    
    def _generate_repeated_fields(self) -> str:
        """Test repeated (array) fields."""
        name = "repeated_fields"
        proto = '''syntax = "proto3";

message RepeatedFields {
  repeated int32 numbers = 1;
  repeated string tags = 2;
  
  message Item {
    string name = 1;
    double price = 2;
  }
  repeated Item items = 3;
}
'''
        data = [
            {
                "numbers": [1, 2, 3, 5, 8, 13, 21],
                "tags": ["important", "urgent", "review"],
                "items": [
                    {"name": "Apple", "price": 1.99},
                    {"name": "Banana", "price": 0.59},
                    {"name": "Orange", "price": 2.49}
                ]
            }
        ]
        return self._create_dataset(name, proto, data)
    
    def _generate_maps(self) -> str:
        """Test map fields."""
        name = "maps"
        proto = '''syntax = "proto3";

message Maps {
  map<string, int32> scores = 1;
  map<string, string> metadata = 2;
  
  message Value {
    double amount = 1;
    string currency = 2;
  }
  map<string, Value> prices = 3;
}
'''
        data = [
            {
                "scores": {"Alice": 95, "Bob": 87, "Charlie": 92},
                "metadata": {"version": "1.0", "author": "test", "status": "active"},
                "prices": {
                    "USD": {"amount": 100.0, "currency": "USD"},
                    "EUR": {"amount": 85.0, "currency": "EUR"}
                }
            }
        ]
        return self._create_dataset(name, proto, data)
    
    def _generate_enums(self) -> str:
        """Test enum types."""
        name = "enums"
        proto = '''syntax = "proto3";

message Enums {
  enum Status {
    UNKNOWN = 0;
    PENDING = 1;
    APPROVED = 2;
    REJECTED = 3;
  }
  
  enum Priority {
    LOW = 0;
    MEDIUM = 1;
    HIGH = 2;
    CRITICAL = 3;
  }
  
  Status status = 1;
  Priority priority = 2;
  string description = 3;
}
'''
        data = [
            {"status": 2, "priority": 3, "description": "Critical approval needed"},
            {"status": 1, "priority": 1, "description": "Awaiting review"}
        ]
        return self._create_dataset(name, proto, data)
    
    def _generate_oneof(self) -> str:
        """Test oneof fields."""
        name = "oneof"
        proto = '''syntax = "proto3";

message Oneof {
  string id = 1;
  
  oneof payload {
    string text_data = 2;
    int32 numeric_data = 3;
    bool flag_data = 4;
  }
}
'''
        data = [
            {"id": "rec1", "text_data": "Hello"},
            {"id": "rec2", "numeric_data": 42},
            {"id": "rec3", "flag_data": True}
        ]
        return self._create_dataset(name, proto, data)
    
    def _generate_optional_fields(self) -> str:
        """Test optional fields (proto3 feature)."""
        name = "optional_fields"
        proto = '''syntax = "proto3";

message OptionalFields {
  string required_field = 1;
  optional string optional_string = 2;
  optional int32 optional_int = 3;
  optional bool optional_bool = 4;
}
'''
        data = [
            {
                "required_field": "always present",
                "optional_string": "sometimes here",
                "optional_int": 100
            },
            {
                "required_field": "also present"
            }
        ]
        return self._create_dataset(name, proto, data)
    
    def _generate_complex_nested(self) -> str:
        """Test complex nested structures."""
        name = "complex_nested"
        proto = '''syntax = "proto3";

message ComplexNested {
  message Person {
    string name = 1;
    int32 age = 2;
    
    message ContactInfo {
      string email = 1;
      repeated string phones = 2;
    }
    ContactInfo contact = 3;
  }
  
  message Department {
    string name = 1;
    repeated Person employees = 2;
    map<string, string> metadata = 3;
  }
  
  string company = 1;
  repeated Department departments = 2;
}
'''
        data = [
            {
                "company": "Tech Corp",
                "departments": [
                    {
                        "name": "Engineering",
                        "employees": [
                            {
                                "name": "Alice",
                                "age": 30,
                                "contact": {
                                    "email": "alice@example.com",
                                    "phones": ["+1-555-0001", "+1-555-0002"]
                                }
                            },
                            {
                                "name": "Bob",
                                "age": 35,
                                "contact": {
                                    "email": "bob@example.com",
                                    "phones": ["+1-555-0003"]
                                }
                            }
                        ],
                        "metadata": {"location": "Building A", "floor": "3"}
                    }
                ]
            }
        ]
        return self._create_dataset(name, proto, data)
