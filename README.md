# TypeScripta

TypeScripta is a simple, scalable monolith for parsing TypeScript source code through ANTLR while keeping the architecture clean enough for future semantic analysis, indexing, and export pipelines.

The project starts from the domain, not from the framework:

* business goal: convert TypeScript source into a stable structural model for downstream tooling
* architectural style: DDD-inspired layered monolith with hexagonal boundaries
* parser engine: ANTLR4 with the public TypeScript grammar
* current delivery channel: CLI that parses a file or a directory, builds Nassi-Shneiderman diagrams, and detects code smells.

## What the system does

Today the system supports:

* **Parsing TypeScript code**
  * parsing one TypeScript file
  * parsing a directory of TypeScript files
  * extracting a lightweight structural model: imports, type declarations, classes, interfaces, functions, variables, and enums
  * reporting syntax diagnostics as part of the contract

* **Control flow extraction**
  * if/else statements with nested branches
  * while loops
  * for loops
  * switch/case statements
  * try-catch-finally blocks

* **Nassi-Shneiderman diagrams**
  * building a Nassi-Shneiderman HTML diagram for one TypeScript file
  * building diagram bundles for entire directories with index page
  * classic NS rendering with SVG triangles for if-blocks
  * depth-coded nested ifs (up to 50 levels with color cycling and Unicode badges ①-㊿)
  * classic case block structure with side-by-side columns
  * dark Tokyo Night-inspired theme with JetBrains Mono font
  * proper text wrapping and responsive layout

* **Code Smell Detection**
  * **13 built-in detectors**:
    * **Comment Density**: Low comment-to-code ratio.
    * **Data Clumps**: Groups of variables that appear together frequently.
    * **Divergent Change**: A class that is modified for many different reasons.
    * **Feature Envy**: Methods that use data from another object more than their own.
    * **Message Chains**: Long chains of method calls (`a.b().c().d()`).
    * **Middle Man**: Classes that mostly delegate to other objects.
    * **Primitive Obsession**: Overuse of primitive types instead of small objects.
    * **Refused Bequest**: Subclasses that don't use inherited methods.
    * **Shotgun Surgery**: A single change that requires touching many files.
    * **Speculative Generality**: Code designed for "future use" that isn't needed yet.
    * **Switch Statements**: Excessive use of `switch` or complex `if-else`.
    * **Temporary Field**: Fields that are only used under certain conditions.
  * JSON reporting with location (file, line, column) and detailed messages.

* **Architecture**
  * keeping parser infrastructure behind ports so the application layer stays independent from ANTLR, filesystem, and CLI details

## Quick Start

1. Install dependencies:

```bash
uv sync --extra dev
```

2. Generate the TypeScript parser from the vendored grammar:

```bash
uv run python scripts/generate_typescript_parser.py
```

3. Parse a single file:

```bash
uv run typescripta parse-file path/to/File.ts
```

4. Parse a directory:

```bash
uv run typescripta parse-dir path/to/project
```

5. Detect code smells:

```bash
uv run typescripta smells path/to/project_or_file
```

6. Build a Nassi-Shneiderman diagram for a TypeScript file:

```bash
uv run typescripta nassi-file path/to/Algorithms.ts --out output/algorithms.nassi.html
```

7. Build Nassi-Shneiderman diagrams for an entire directory:

```bash
uv run typescripta nassi-dir path/to/project --out output/nassi-bundle
```

## Architecture

The codebase is split into four explicit layers:

* `domain`: domain model, invariants, ports, and domain events
* `application`: use cases and DTOs
* `infrastructure`: ANTLR adapter, filesystem adapters, event publishing, smell detectors
* `presentation`: CLI contract

See the full design docs in `docs/`.
