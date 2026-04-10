# envcrypt (Python)

Python library for loading encrypted `.env` files. Compatible with the Rust `envcrypt` CLI tool.

## Installation

```bash
pip install -e .
# or
pip install envcrypt
```

## Usage

### Basic usage (from config file)

```python
import envcrypt
import os

# Load key from ~/.envcrypt.yaml, decrypt .env, set env vars
envcrypt.load(".env")

# Access as normal
db_url = os.environ["DATABASE_URL"]
```

### With explicit key

```python
from envcrypt import EnvcryptLoader

# 64-char hex key (32 bytes)
loader = EnvcryptLoader.from_key("your-64-char-hex-key...")
loader.load(".env")

# Or with litcrypt-style obfuscation (your own implementation)
from myapp.secrets import get_key
loader = EnvcryptLoader.from_key(get_key())
loader.load(".env")
```

### Encrypt/decrypt content

```python
from envcrypt import EnvcryptLoader

loader = EnvcryptLoader.from_config()

# Encrypt
content = open(".env").read()
encrypted = loader.encrypt_content(content)
print(encrypted)

# Decrypt
decrypted = loader.decrypt_content(encrypted)
print(decrypted)
```

### Single value encrypt/decrypt

```python
from envcrypt import EnvcryptLoader

loader = EnvcryptLoader.from_config()

encrypted = loader.encrypt("my-secret")
print(encrypted)  # encrypted:base64...

decrypted = loader.decrypt(encrypted)
print(decrypted)  # my-secret
```

## Compatibility

This library uses the same encryption format as the Rust `envcrypt` CLI:

- **Algorithm**: AES-256-GCM
- **Key**: 32 bytes (64 hex chars)
- **Nonce**: 12 bytes (random, prepended to ciphertext)
- **Format**: `encrypted:<base64(nonce + ciphertext + tag)>`

Files encrypted with the CLI can be loaded with Python and vice versa.

## Config File

Default location: `~/.envcrypt.yaml`

```yaml
key: "64-character-hex-encoded-key..."
```

## License

MIT
