# envcrypt (TypeScript)

TypeScript/JavaScript library for loading encrypted `.env` files. Compatible with the Rust `envcrypt` CLI tool.

## Installation

```bash
npm install envcrypt
```

## Usage

### Basic usage (from config file)

```typescript
import { loadFromConfig } from "envcrypt";

// Load key from ~/.envcrypt.yaml, decrypt .env, set env vars
loadFromConfig(".env");

// Access as normal
console.log(process.env.DATABASE_URL);
```

### With explicit key

```typescript
import { load } from "envcrypt";

// 64-char hex key (32 bytes)
load(".env", { key: "your-64-char-hex-key..." });
```

### Using the class directly

```typescript
import { EnvcryptLoader } from "envcrypt";

// From config file
const loader = EnvcryptLoader.fromConfig();

// Or from key
const loader = EnvcryptLoader.fromKey("your-64-char-hex-key...");

// Load .env and set process.env
const vars = loader.load(".env");
```

### Encrypt/decrypt content

```typescript
import { EnvcryptLoader } from "envcrypt";

const loader = EnvcryptLoader.fromConfig();

// Encrypt entire .env content
const encrypted = loader.encryptContent(content);

// Decrypt entire .env content
const decrypted = loader.decryptContent(encrypted);
```

### Single value encrypt/decrypt

```typescript
import { EnvcryptLoader } from "envcrypt";

const loader = EnvcryptLoader.fromConfig();

const encrypted = loader.encrypt("my-secret");
console.log(encrypted); // encrypted:base64...

const decrypted = loader.decrypt(encrypted);
console.log(decrypted); // my-secret
```

### Generate a key

```typescript
import { EnvcryptLoader } from "envcrypt";

const key = EnvcryptLoader.generateKey();
console.log(key); // 64-char hex string
```

## Compatibility

This library uses the same encryption format as the Rust `envcrypt` CLI:

- **Algorithm**: AES-256-GCM
- **Key**: 32 bytes (64 hex chars)
- **Nonce**: 12 bytes (random, prepended to ciphertext)
- **Format**: `encrypted:<base64(nonce + ciphertext + tag)>`

Files encrypted with the CLI can be loaded with TypeScript and vice versa.

## Config File

Default location: `~/.envcrypt.yaml`

```yaml
key: "64-character-hex-encoded-key..."
```

## License

MIT
