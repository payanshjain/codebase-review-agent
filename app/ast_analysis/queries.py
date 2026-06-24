"""
Per-language tree-sitter query patterns for extracting semantic code symbols.

Each query captures:
- Function/method definitions with their names
- Class definitions with their names
- Import statements

Queries use tree-sitter's S-expression pattern language with named captures.
The capture names follow a convention:
    @definition.function  — a function or method definition node
    @name.function        — the identifier node for the function name
    @definition.class     — a class definition node
    @name.class           — the identifier node for the class name
    @import               — an import statement node

Adding a new language:
    1. Add the query string to LANGUAGE_QUERIES below.
    2. Add the extension mapping in languages.py.
    3. Test with the tree-sitter playground (https://tree-sitter.github.io/tree-sitter/playground).
"""

# ── Python ─────────────────────────────────────────────────────────

_PYTHON_QUERY = """
; Top-level and nested function definitions
(function_definition
  name: (identifier) @name.function) @definition.function

; Class definitions
(class_definition
  name: (identifier) @name.class) @definition.class

; Import statements
(import_statement) @import
(import_from_statement) @import
"""

# ── JavaScript / JSX ──────────────────────────────────────────────

_JAVASCRIPT_QUERY = """
; Regular function declarations
(function_declaration
  name: (identifier) @name.function) @definition.function

; Arrow functions assigned to variables
(lexical_declaration
  (variable_declarator
    name: (identifier) @name.function
    value: (arrow_function) @definition.function))

; Class declarations
(class_declaration
  name: (identifier) @name.class) @definition.class

; Method definitions inside classes
(method_definition
  name: (property_identifier) @name.function) @definition.function

; Import statements
(import_statement) @import
"""

# ── TypeScript / TSX ──────────────────────────────────────────────

_TYPESCRIPT_QUERY = """
; Regular function declarations
(function_declaration
  name: (identifier) @name.function) @definition.function

; Arrow functions assigned to variables
(lexical_declaration
  (variable_declarator
    name: (identifier) @name.function
    value: (arrow_function) @definition.function))

; Class declarations
(class_declaration
  name: (type_identifier) @name.class) @definition.class

; Method definitions inside classes
(method_definition
  name: (property_identifier) @name.function) @definition.function

; Interface declarations (useful for understanding contracts)
(interface_declaration
  name: (type_identifier) @name.class) @definition.class

; Import statements
(import_statement) @import
"""

# ── Java ──────────────────────────────────────────────────────────

_JAVA_QUERY = """
; Method declarations
(method_declaration
  name: (identifier) @name.function) @definition.function

; Constructor declarations
(constructor_declaration
  name: (identifier) @name.function) @definition.function

; Class declarations
(class_declaration
  name: (identifier) @name.class) @definition.class

; Interface declarations
(interface_declaration
  name: (identifier) @name.class) @definition.class

; Import declarations
(import_declaration) @import
"""

# ── Go ────────────────────────────────────────────────────────────

_GO_QUERY = """
; Function declarations
(function_declaration
  name: (identifier) @name.function) @definition.function

; Method declarations (receiver functions)
(method_declaration
  name: (field_identifier) @name.function) @definition.function

; Type declarations (structs, interfaces)
(type_declaration
  (type_spec
    name: (type_identifier) @name.class)) @definition.class

; Import declarations
(import_declaration) @import
"""

# ── Rust ──────────────────────────────────────────────────────────

_RUST_QUERY = """
; Function definitions
(function_item
  name: (identifier) @name.function) @definition.function

; Struct definitions
(struct_item
  name: (type_identifier) @name.class) @definition.class

; Enum definitions
(enum_item
  name: (type_identifier) @name.class) @definition.class

; Impl blocks
(impl_item
  type: (type_identifier) @name.class) @definition.class

; Trait definitions
(trait_item
  name: (type_identifier) @name.class) @definition.class

; Use statements (imports)
(use_declaration) @import
"""


# ── Registry ──────────────────────────────────────────────────────

LANGUAGE_QUERIES: dict[str, str] = {
    "python": _PYTHON_QUERY,
    "javascript": _JAVASCRIPT_QUERY,
    "typescript": _TYPESCRIPT_QUERY,
    "java": _JAVA_QUERY,
    "go": _GO_QUERY,
    "rust": _RUST_QUERY,
}


def get_query_for_language(language: str) -> str | None:
    """Return the tree-sitter query string for a language, or None if unsupported."""
    return LANGUAGE_QUERIES.get(language)
