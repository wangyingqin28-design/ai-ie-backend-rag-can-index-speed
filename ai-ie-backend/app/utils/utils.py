import hashlib
from uuid_extensions import uuid7
import random

def calculate_file_hash(file_content: bytes) -> str:
    """
    Calculate SHA-256 hash of original file content for duplicate detection.

    Args:
        file_content: Original file content as bytes (raw file data)

    Returns:
        Hexadecimal string of SHA-256 hash
    """
    return hashlib.sha256(file_content).hexdigest()


# Helper function for random id generation
def random_id():
    """Generate a random ID string"""
    return "".join(random.sample(uuid7().hex, 16))    

def generate_vector_db_collection_name(collection_id) -> str:
    return str(collection_id)    