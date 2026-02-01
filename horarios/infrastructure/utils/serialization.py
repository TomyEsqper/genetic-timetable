import dataclasses
from typing import Any, Dict, List, Set, Tuple
from decimal import Decimal
import datetime

def make_json_serializable(obj: Any) -> Any:
    """
    Recursively converts objects to JSON-serializable formats.
    Handles dataclasses, sets, tuples (as lists), and custom objects with to_dict/as_dict.
    """
    if obj is None:
        return None
    
    if dataclasses.is_dataclass(obj):
        return make_json_serializable(dataclasses.asdict(obj))
    
    if isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    
    if isinstance(obj, set):
        return [make_json_serializable(item) for item in list(obj)]
    
    if isinstance(obj, dict):
        # Handle non-string keys by converting them to string
        new_dict = {}
        for k, v in obj.items():
            key = str(k) if not isinstance(k, str) else k
            new_dict[key] = make_json_serializable(v)
        return new_dict
    
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    
    if isinstance(obj, Decimal):
        return float(obj)
        
    if hasattr(obj, 'to_dict') and callable(obj.to_dict):
        return make_json_serializable(obj.to_dict())
        
    if hasattr(obj, '__dict__'):
        return make_json_serializable(obj.__dict__)
        
    return obj
