# Apparel CSV Working Rules

- Use Python with Polars for dataframe transformations. Do not introduce pandas unless the user explicitly requires it.
- Treat CSV content as potentially personal or sensitive data. Inspect and log the minimum needed; never expose raw personal rows in reports, chat output, fixtures, or logs.
- Protect source files. Never overwrite an original CSV unless the user explicitly requests that exact overwrite after being told the target path and risk. Default to a clearly named new output file.
- Use deterministic transforms and stable output ordering. Document any ordering, deduplication, aggregation, or tie-breaking rule that affects results.
- Parse delimiters, encodings, dates, decimals, null markers, and schemas explicitly when known. Do not rely on silent inference for risky columns.
- Prefer `scan_csv` and Polars expressions over eager loading, Python row loops, or Python UDFs when practical.
- Use robust parsing with explicit handling of malformed values. Never silently discard or coerce data without a stated rule.
- For writes, prefer a temporary file in the destination directory, validate it, then atomically replace the intended output with `os.replace` when practical.
- Do not invent business rules, schemas, keys, null policies, or file-format assumptions. Surface unknowns and ask for clarification when they affect correctness.
- Validate in proportion to risk: schema, row counts, key uniqueness, null policy, aggregate or quantity conservation, delimiter/encoding, deterministic reruns, and original-file hash as applicable.
- Keep dependencies local to the project environment. Do not install packages globally.
- Do not create broad project scaffolding such as `pyproject.toml`, `src/`, or `tests/` unless explicitly requested.
