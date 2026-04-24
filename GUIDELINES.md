# AI Behavioral Guidelines

This document contains rules and preferences for any AI coding assistant when working on this project.

## Formatting Rules

- **No Trailing Whitespace**: All blank lines must be truly empty and contain no spaces or tabs.
- **Consistent Indentation**: Always use 4 spaces for indentation. Do not use tabs and fix any tabbing found in the codebase.
- **Write DRY Code**: Do not repeat yourself. Extract common logic into functions and reuse them.
- **Consistent Naming**: Use `snake_case` for variables and functions, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.

## Code Structure Rules

- **Modular Design**: Break down code into small, focused functions and classes.
- **Single Responsibility**: Each function and class should have a single responsibility.
- **Separation of Concerns**: Separate logic from presentation and data access layers.
- **Avoid Deep Nesting**: Limit nested code to a maximum of 3 levels to maintain readability.

## Programming Rules

- **Favor Immutability**: Use immutable data structures when possible to prevent side effects.
- **Explicit Type Hinting**: Always use type hints for function parameters and return values.
- **Error Handling**: Use `try-except` blocks for error handling and provide meaningful error messages.
- **Use Built-ins**: Prefer built-in functions and modules over custom implementations when available.