"""
envcrypt - Load encrypted .env files in Python

Compatible with the Rust envcrypt CLI tool.
Uses AES-256-GCM encryption.
"""

from .loader import EnvcryptLoader, load, load_from_config

__version__ = "0.1.0"
__all__ = ["EnvcryptLoader", "load", "load_from_config"]
