"""
Validate that PB3 and Parquet files contain equivalent data.
"""
from pathlib import Path
from typing import Any, Dict, List, Tuple
import sys
import pyarrow.parquet as pq
import pandas as pd


class ValidationResult:
    """Result of validation comparison."""
    
    def __init__(self, success: bool, message: str, details: List[str] = None):
        self.success = success
        self.message = message
        self.details = details or []
    
    def __str__(self) -> str:
        result = f"{'✓' if self.success else '✗'} {self.message}"
        if self.details:
            result += "\n  " + "\n  ".join(self.details)
        return result


class DataValidator:
    """Validate PB3 to Parquet conversion accuracy."""
    
    def validate(
        self,
        pb3_file: Path,
        parquet_file: Path,
        proto_module_path: Path,
        message_class_name: str
    ) -> ValidationResult:
        """
        Validate that data in PB3 and Parquet files match.
        
        Args:
            pb3_file: Path to original .pb3 file
            parquet_file: Path to converted .parquet file
            proto_module_path: Path to directory containing compiled proto
            message_class_name: Name of the protobuf message class
            
        Returns:
            ValidationResult with success status and details
        """
        try:
            # Read PB3 data
            pb_records = self._read_pb3(pb3_file, proto_module_path, message_class_name)
            
            # Read Parquet data
            parquet_df = pq.read_table(parquet_file).to_pandas()
            
            # Compare record counts
            if len(pb_records) != len(parquet_df):
                return ValidationResult(
                    success=False,
                    message=f"Record count mismatch: PB3={len(pb_records)}, Parquet={len(parquet_df)}"
                )
            
            # Compare data row by row
            mismatches = []
            for idx, pb_record in enumerate(pb_records):
                parquet_record = self._normalize_parquet_record(
                    parquet_df.iloc[idx].to_dict()
                )
                pb_dict = self._message_to_dict(pb_record)
                
                diffs = self._compare_records(pb_dict, parquet_record, f"row {idx}")
                mismatches.extend(diffs)
            
            if mismatches:
                return ValidationResult(
                    success=False,
                    message=f"Data validation failed with {len(mismatches)} mismatches",
                    details=mismatches[:10]  # Limit to first 10 mismatches
                )
            
            return ValidationResult(
                success=True,
                message=f"Validation passed: {len(pb_records)} records match perfectly"
            )
            
        except Exception as e:
            return ValidationResult(
                success=False,
                message=f"Validation error: {str(e)}"
            )
    
    def _normalize_parquet_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a parquet record to use Python native types."""
        return {k: self._normalize_value(v) for k, v in record.items()}

    def _normalize_value(self, value: Any) -> Any:
        """Recursively convert numpy/pandas types to Python native types."""
        import numpy as np
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass  # value is array-like; handle below
        if isinstance(value, np.ndarray):
            return [self._normalize_value(item) for item in value]
        if isinstance(value, (list, tuple)):
            return [self._normalize_value(item) for item in value]
        if isinstance(value, dict):
            return {k: self._normalize_value(v) for k, v in value.items()}
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.bool_):
            return bool(value)
        return value

    def _is_na(self, value: Any) -> bool:
        """Safe NA check that works for both scalars and arrays."""
        try:
            result = pd.isna(value)
            # pd.isna returns bool for scalars, array for array-like
            return bool(result)
        except (TypeError, ValueError):
            return False

    def _read_pb3(
        self, 
        pb3_file: Path, 
        proto_module_path: Path, 
        message_class_name: str
    ) -> List[Any]:
        """Read PB3 file (varint length-delimited format) and return message objects."""
        sys.path.insert(0, str(proto_module_path))
        
        try:
            proto_module_name = proto_module_path.name
            pb_module = __import__(f"{proto_module_name}_pb2")
            message_class = getattr(pb_module, message_class_name)
            
            records = []
            with open(pb3_file, 'rb') as f:
                while True:
                    length = self._read_varint(f)
                    if length is None:
                        break
                    msg_bytes = f.read(length)
                    if len(msg_bytes) != length:
                        break
                    msg = message_class()
                    msg.ParseFromString(msg_bytes)
                    records.append(msg)
            
            return records
        finally:
            if str(proto_module_path) in sys.path:
                sys.path.remove(str(proto_module_path))

    def _read_varint(self, f) -> int:
        """Read a varint from file; returns None at EOF."""
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
    
    def _message_to_dict(self, message: Any) -> Dict[str, Any]:
        """Convert protobuf message to dictionary for comparison."""
        result = {}
        
        for field in message.DESCRIPTOR.fields:
            value = getattr(message, field.name)
            is_map = bool(field.message_type and field.message_type.GetOptions().map_entry)
            is_repeated = not is_map and self._is_repeated_value(value)
            
            if field.message_type:
                if is_map:
                    # Recursively convert message values within the map
                    d = {}
                    for k, v in value.items():
                        d[k] = self._message_to_dict(v) if hasattr(v, 'DESCRIPTOR') else v
                    result[field.name] = d
                elif is_repeated:
                    result[field.name] = [self._message_to_dict(item) for item in value]
                else:
                    if message.HasField(field.name):
                        result[field.name] = self._message_to_dict(value)
                    else:
                        result[field.name] = None
            elif is_repeated:
                result[field.name] = list(value)
            else:
                # Use try/except for field.type since _upb may not expose it
                try:
                    from google.protobuf.descriptor import FieldDescriptor
                    if field.type == FieldDescriptor.TYPE_BYTES:
                        result[field.name] = bytes(value)
                    elif field.type == FieldDescriptor.TYPE_ENUM:
                        result[field.name] = int(value)
                    else:
                        result[field.name] = value
                except AttributeError:
                    # Fallback: detect by value type
                    if isinstance(value, bytes):
                        result[field.name] = value
                    else:
                        result[field.name] = value
        
        return result

    def _is_repeated_value(self, value: Any) -> bool:
        """Check if a field value is a repeated (list) container."""
        return 'Repeated' in type(value).__name__
    
    def _compare_records(
        self, 
        pb_data: Dict[str, Any], 
        parquet_data: Dict[str, Any],
        path: str
    ) -> List[str]:
        """Compare two records and return list of differences."""
        differences = []
        
        # Check all keys from pb_data
        for key in pb_data.keys():
            if key not in parquet_data:
                differences.append(f"{path}.{key}: missing in Parquet")
                continue
            
            pb_value = pb_data[key]
            pq_value = parquet_data[key]
            
            # Handle None values
            if pb_value is None and self._is_na(pq_value):
                continue
            if pb_value is None or self._is_na(pq_value):
                differences.append(
                    f"{path}.{key}: None mismatch (PB={pb_value}, Parquet={pq_value})"
                )
                continue
            
            # Compare based on type
            if isinstance(pb_value, dict):
                # Parquet maps come back as list of (key, value) tuples — normalize to dict
                if isinstance(pq_value, list):
                    try:
                        pq_value = dict(pq_value)
                    except (TypeError, ValueError):
                        pass
                if not isinstance(pq_value, dict):
                    differences.append(
                        f"{path}.{key}: type mismatch (PB=dict, Parquet={type(pq_value).__name__})"
                    )
                else:
                    differences.extend(self._compare_records(pb_value, pq_value, f"{path}.{key}"))
            
            elif isinstance(pb_value, list):
                if not isinstance(pq_value, list):
                    differences.append(
                        f"{path}.{key}: type mismatch (PB=list, Parquet={type(pq_value).__name__})"
                    )
                elif len(pb_value) != len(pq_value):
                    differences.append(
                        f"{path}.{key}: list length mismatch (PB={len(pb_value)}, Parquet={len(pq_value)})"
                    )
                else:
                    for i, (pb_item, pq_item) in enumerate(zip(pb_value, pq_value)):
                        if isinstance(pb_item, dict):
                            differences.extend(
                                self._compare_records(pb_item, pq_item, f"{path}.{key}[{i}]")
                            )
                        elif not self._values_equal(pb_item, pq_item):
                            differences.append(
                                f"{path}.{key}[{i}]: value mismatch (PB={pb_item}, Parquet={pq_item})"
                            )
            
            elif isinstance(pb_value, bytes):
                # Compare bytes
                pq_bytes = pq_value if isinstance(pq_value, bytes) else bytes(pq_value)
                if pb_value != pq_bytes:
                    differences.append(
                        f"{path}.{key}: bytes mismatch"
                    )
            
            else:
                # Scalar comparison
                if not self._values_equal(pb_value, pq_value):
                    differences.append(
                        f"{path}.{key}: value mismatch (PB={pb_value}, Parquet={pq_value})"
                    )
        
        return differences
    
    def _values_equal(self, v1: Any, v2: Any) -> bool:
        """Check if two scalar values are equal with type tolerance."""
        # Handle numeric comparisons with tolerance for float precision
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            if isinstance(v1, float) or isinstance(v2, float):
                return abs(float(v1) - float(v2)) < 1e-6
            return int(v1) == int(v2)
        
        # Handle string comparisons
        if isinstance(v1, str) and isinstance(v2, str):
            return v1 == v2
        
        # Handle boolean
        if isinstance(v1, bool) and isinstance(v2, bool):
            return v1 == v2
        
        # Default equality
        return v1 == v2
