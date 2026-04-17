# Mimicry Pseudocode DSL v1

## Overview
A human-readable, AI-parseable workflow description language for browser automation.

## Syntax

### Workflow Declaration
```
WORKFLOW "name" {
  ...statements
}
```

### Navigation
```
OPEN "https://example.com"
BACK
FORWARD
RELOAD
```

### Element Actions
```
CLICK "selector"
DBLCLICK "selector"
TYPE "selector" "text"
CLEAR "selector"
SELECT "selector" "value"
HOVER "selector"
SCROLL "selector" direction=down amount=300
FOCUS "selector"
```

### Waiting
```
WAIT selector="selector" timeout=5s
WAIT url_contains="path" timeout=10s
WAIT time=2s
```

### Data Extraction
```
EXTRACT text="selector" into=$variable
EXTRACT attr="selector" name="href" into=$link
EXTRACT count="selector" into=$num
```

### Control Flow
```
IF condition {
  ...statements
} ELSE {
  ...statements
}

LOOP items="selector" as=$item max=10 {
  ...statements
}

LOOP count=5 as=$i {
  ...statements
}

LOOP while=exists("selector") max=100 {
  ...statements
}
```

### Variables
```
SET $name = "value"
SET $count = 0
```

### Utilities
```
SCREENSHOT "filename.png"
LOG "message" $variable
SLEEP 1s
FAIL "error message"
```

### Conditions
Conditions can use:
- `exists("selector")` — element exists in DOM
- `visible("selector")` — element is visible
- `text("selector") == "value"` — text content match
- `$variable == "value"` — variable comparison
- `url_contains("path")` — URL check
- `not`, `and`, `or` — logical operators

### Selector Chaining
```
CLICK $item >> ".child-selector"
```
The `>>` operator scopes the right selector within the left element.

## Examples

### Login Flow
```
WORKFLOW "Login" {
  OPEN "https://app.example.com/login"
  WAIT selector="#email" timeout=5s
  TYPE "#email" "user@example.com"
  TYPE "#password" "secret"
  CLICK "button[type=submit]"
  WAIT url_contains="/dashboard" timeout=10s
}
```

### Data Scraping
```
WORKFLOW "Scrape Products" {
  OPEN "https://shop.example.com"
  WAIT selector=".product-list" timeout=10s
  
  LOOP items=".product-card" as=$card max=50 {
    EXTRACT text=$card >> ".title" into=$title
    EXTRACT text=$card >> ".price" into=$price
    LOG "Product:" $title $price
  }
}
```

## JSON Mapping
Each pseudocode statement maps to a workflow node:

| Pseudocode | Node Type | Key Fields |
|-----------|-----------|------------|
| OPEN, CLICK, TYPE, etc. | action | action, selector, value |
| IF/ELSE | condition | condition, selector |
| LOOP | loop | loopType, selector, count, variable |
| Nested blocks | group | children |
