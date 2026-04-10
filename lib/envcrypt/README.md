# envcrypt

Secure your `.env` files from accidental leaks.

`.env` files often contain sensitive secrets like API keys, database credentials, and tokens. In plain text, these are vulnerable to accidental exposure, a misplaced `git add`, a screen share, or an AI coding agent reading your project files can all leak secrets unintentionally.

Envcrypt solves this by encrypting your `.env` values in place. The workflow is simple:

1. **Encrypt** your `.env` file using the `envcrypt` CLI tool
2. **Read** encrypted values directly in your application — decryption happens transparently at runtime

This is especially useful in the era of agentic coding, where AI assistants routinely read project files. With envcrypt, your `.env` file can stay in your project directory without exposing raw secrets to any tool or agent that accesses it.

## Features

- AES-256-GCM encryption (authenticated encryption)
- Encrypted values prefixed with `encrypted:` for easy identification
- CLI tool for encrypting/decrypting `.env` files
- Libraries for Rust, TypeScript/JavaScript, and Python
- Cross-language compatibility — files encrypted with the CLI can be loaded from any supported language
- Key stored in `~/.envcrypt.yaml`

## Project Structure

```
envcrypt/
├── cli/                  # CLI tool (Rust)
└── libs/
    ├── rust/             # Rust library (envcrypt-lib)
    ├── typescript/       # TypeScript/JavaScript library
    └── python/           # Python library
```

## Installation

### CLI

```bash
cargo install --path cli
```

### Libraries

- **Rust**: `envcrypt-lib = { path = "libs/rust" }` in your `Cargo.toml`
- **TypeScript/JavaScript**: `npm install envcrypt`
- **Python**: `pip install envcrypt`

See each library's README for detailed usage:
- [Rust library](libs/rust/)
- [TypeScript library](libs/typescript/)
- [Python library](libs/python/)

## CLI Usage

### Initialize (first time)

```bash
# Generate random key
envcrypt init --generate

# Or provide your own key (64 hex chars = 32 bytes)
envcrypt init --key "your-64-character-hex-key-here..."
```

### Encrypt a .env file

```bash
# Output to stdout
envcrypt encrypt .env

# Output to file
envcrypt encrypt .env -o .env.encrypted

# Modify in-place
envcrypt encrypt .env --in-place
```

### Decrypt a .env file

```bash
# Output to stdout
envcrypt decrypt .env.encrypted

# Output to file
envcrypt decrypt .env.encrypted -o .env

# Modify in-place
envcrypt decrypt .env.encrypted --in-place
```

### Encrypt/decrypt single values

```bash
envcrypt encrypt-value "my-secret"
# Output: encrypted:base64...

envcrypt decrypt-value "encrypted:base64..."
# Output: my-secret
```

### Check status

```bash
envcrypt status
```

## Quick Start (Library)

### Rust

```rust
use envcrypt_lib::EnvcryptLoader;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let loader = EnvcryptLoader::from_config(None)?;
    loader.load(".env")?;
    let db_url = std::env::var("DATABASE_URL")?;
    Ok(())
}
```

### TypeScript

```typescript
import { loadFromConfig } from "envcrypt";

loadFromConfig(".env");
console.log(process.env.DATABASE_URL);
```

### Python

```python
import envcrypt
import os

envcrypt.load(".env")
db_url = os.environ["DATABASE_URL"]
```

## .env File Format

```env
# Comments are preserved
DATABASE_URL=encrypted:base64encodeddata...
API_KEY=encrypted:base64encodeddata...
PLAIN_VALUE=this-is-not-encrypted
```

Encrypted values have the `encrypted:` prefix. Plain values are passed through as-is.

## Security

- **Algorithm**: AES-256-GCM (authenticated encryption with associated data)
- **Nonce**: 12 bytes, randomly generated per encryption
- **Key**: 32 bytes (256 bits), stored in config file
- **Format**: `encrypted:<base64(nonce + ciphertext + tag)>`

## Config File

Location: `~/.envcrypt.yaml`

```yaml
key: "64-character-hex-encoded-key..."
```

## License

MIT
