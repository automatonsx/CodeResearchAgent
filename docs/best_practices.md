# Scout Best Practices Knowledge Base

> **Purpose:** Authoritative catalogue of the coding practices that Scout enforces and cites.  
> **Format:** Each practice has a machine ID (used in `best_practices.json` and RAG), a principle,
> a citation, and the tool rules that automatically detect violations.  
> **Update:** Add entries here **and** in `backend/corpus/best_practices.json`, then
> rebuild the ChromaDB index: `python backend/corpus/build_index.py`

---

## Contents

- [Security](#security)
- [Code Quality](#code-quality)
- [Architecture & Design](#architecture--design)
- [Testing](#testing)
- [Observability & Logging](#observability--logging)
- [JavaScript / TypeScript](#javascript--typescript)
- [API Design](#api-design)

---

## Security

| ID | Practice | Hook? |
|----|----------|-------|
| `bp-secrets` | Never hardcode secrets | SCAN-SECRET |
| `bp-sql-injection` | Use parameterized queries | S608 |
| `bp-shell-injection` | Avoid `shell=True` with untrusted input | S602, S605 |
| `bp-eval` | Do not use `eval`/`exec` on dynamic input | S307, SCAN-EVAL |
| `bp-input-validation` | Validate and sanitize external input | — |
| `bp-tls-verify` | Never disable TLS certificate verification | S501 |
| `bp-weak-hash` | Never use MD5 or SHA-1 for security purposes | S324, SCAN-MD5 |
| `bp-path-traversal` | Validate file paths against a trusted root | — |
| `bp-xss-innerhtml` | Do not assign to `innerHTML` with untrusted content | SCAN-INNERHTML |
| `bp-xss-docwrite` | Avoid `document.write` with dynamic content | SCAN-DOC-WRITE |
| `bp-csrf` | Protect state-changing endpoints against CSRF | — |
| `bp-least-privilege` | Apply least-privilege access to resources | — |
| `bp-auth-info-leak` | Use generic error messages for authentication failures | — |
| `bp-dependencies` | Keep dependencies up to date and audited | — |
| `bp-no-sensitive-response` | Never expose sensitive data in API responses | — |
| `bp-rate-limiting` | Rate-limit sensitive endpoints | — |

---

### bp-secrets — Never hardcode secrets

**Principle:** Credentials, API keys, and passwords must never be committed in source code. Load them
from environment variables or a secrets manager so they can be rotated without code changes.

**Why it matters:** A secret that ships in a commit is effectively public — git history is rarely
cleaned. Rotation requires a code change, a review, and a deploy, creating a wide exposure window.

**Citation:** [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

**Detected by:** Bandit S105, S106, S107 · custom `SCAN-SECRET` pattern

```python
# ✗ Never
DB_PASSWORD = "hunter2"
API_KEY = "sk-live-abc123"

# ✓ Always
import os
DB_PASSWORD = os.environ["DB_PASSWORD"]
API_KEY = os.environ["API_KEY"]
```

---

### bp-sql-injection — Use parameterized queries

**Principle:** Build SQL with bound parameters, never string concatenation or f-strings on user
input. Parameterization is the primary defense against SQL injection (OWASP A03).

**Why it matters:** SQL injection is consistently ranked in the OWASP Top 10 and has caused some of
the largest data breaches in history. String formatting gives an attacker full query control.

**Citation:** [OWASP Top 10 — A03:2021 Injection](https://owasp.org/Top10/A03_2021-Injection/)

**Detected by:** Ruff S608 · semgrep `python.lang.security.audit.formatted-sql-query`

```python
# ✗ Never
cursor.execute(f"SELECT * FROM users WHERE name = '{username}'")

# ✓ Always
cursor.execute("SELECT * FROM users WHERE name = %s", (username,))
```

---

### bp-shell-injection — Avoid `shell=True` with untrusted input

**Principle:** Passing `shell=True` to subprocess expands a shell, so any metacharacter in an
argument (`;`, `|`, `&&`) executes additional commands. Prefer a list of arguments so the OS
exec'es the program directly.

**Citation:** [Python docs — subprocess security](https://docs.python.org/3/library/subprocess.html#security-considerations)

**Detected by:** Bandit S602, S605

```python
# ✗ Never
subprocess.run(f"ping {host}", shell=True)

# ✓ Always
subprocess.run(["ping", host])
```

---

### bp-eval — Do not use `eval`/`exec` on dynamic input

**Principle:** `eval` and `exec` execute arbitrary Python. Use `ast.literal_eval` for data literals,
or an explicit dispatch table for behavior switching.

**Citation:** [Python docs — ast.literal_eval](https://docs.python.org/3/library/ast.html#ast.literal_eval) · Bandit B307

**Detected by:** Bandit S307 · custom `SCAN-EVAL`

```python
# ✗ Never
return eval(user_expression)

# ✓ Always
import ast
return ast.literal_eval(user_expression)
```

---

### bp-tls-verify — Never disable TLS certificate verification

**Principle:** `verify=False` in requests silently exposes all HTTPS traffic to man-in-the-middle
attacks. Certificate issues must be fixed at the infrastructure level (installing the right CA),
not suppressed in code.

**Citation:** [OWASP TLS Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html) · Bandit B501

**Detected by:** Bandit S501

```python
# ✗ Never
requests.get(url, verify=False)

# ✓ Always
requests.get(url)                        # production
requests.get(url, verify="/path/to/ca")  # custom CA
```

---

### bp-weak-hash — Never use MD5 or SHA-1 for security purposes

**Principle:** MD5 and SHA-1 are cryptographically broken. Use SHA-256 or higher for integrity
checks; use bcrypt/argon2 for passwords.

**Citation:** [NIST SP 800-131A](https://csrc.nist.gov/publications/detail/sp/800-131a/rev-2/final) · [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)

**Detected by:** Bandit S324 · custom `SCAN-MD5`

```python
# ✗ Never
hashlib.md5(data).hexdigest()
hashlib.sha1(data).hexdigest()

# ✓ Always
hashlib.sha256(data).hexdigest()
```

---

### bp-xss-innerhtml — Do not assign to `innerHTML` with untrusted content

**Principle:** `element.innerHTML = userContent` executes embedded scripts in most browsers. Use
`textContent` for plain text, or DOMPurify to sanitize HTML before insertion.

**Citation:** [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)

**Detected by:** custom `SCAN-INNERHTML`

```js
// ✗ Never
div.innerHTML = userComment;

// ✓ Always (text)
div.textContent = userComment;

// ✓ Always (HTML with sanitizer)
import DOMPurify from 'dompurify';
div.innerHTML = DOMPurify.sanitize(userComment);
```

---

### bp-no-sensitive-logs — Never log sensitive data

**Principle:** Passwords, tokens, credit card numbers, and PII must never appear in log output.
Redact or omit them; log IDs instead of values.

**Why it matters:** Log aggregators often have weaker access controls than databases, and logs are
retained longer than app data. A leaked log file exposes credentials in plaintext.

**Citation:** [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) · GDPR Article 32

```python
# ✗ Never
logger.debug(f"Login: user={email} pass={password}")

# ✓ Always
logger.debug(f"Login attempt: user_id={user_id}")
```

---

## Code Quality

| ID | Practice | Tool Rules |
|----|----------|------------|
| `bp-bare-except` | Never use bare `except` | E722 |
| `bp-swallow-exception` | Don't silently swallow exceptions | S110 |
| `bp-mutable-default` | Avoid mutable default arguments | B006, AST-MUT |
| `bp-complexity` | Keep cyclomatic complexity ≤ 10 | C901, AST-CX |
| `bp-dead-code` | Remove dead / unused code | F401, F841 |
| `bp-docstrings` | Document public functions | AST-DOC |
| `bp-type-hints` | Add type hints to public APIs | — |
| `bp-magic-numbers` | Replace magic numbers with named constants | — |
| `bp-long-functions` | Functions ≤ 40–50 lines | AST-LEN |
| `bp-deep-nesting` | Avoid more than 3 nesting levels | — |
| `bp-global-state` | Avoid global mutable state | — |
| `bp-early-return` | Use guard clauses and early return | — |
| `bp-immutability` | Prefer immutable data structures | — |
| `bp-context-managers` | Use context managers for resource lifecycle | — |

---

### bp-bare-except — Never use bare `except`

**Principle:** A bare `except:` catches everything including `KeyboardInterrupt` and `SystemExit`,
hiding real bugs and making the program impossible to interrupt. Catch only the exceptions you
expect and can handle.

**Citation:** [PEP 8 — Programming Recommendations](https://peps.python.org/pep-0008/#programming-recommendations)

**Detected by:** Ruff E722

```python
# ✗ Never
try:
    process()
except:
    pass

# ✓ Always
try:
    process()
except ValueError as e:
    logger.warning("Invalid value: %s", e)
```

---

### bp-mutable-default — Avoid mutable default arguments

**Principle:** A list or dict default is evaluated once at function definition time and shared
across all calls. The container accumulates state between invocations in ways that are very
hard to debug.

**Citation:** [Python Common Gotchas](https://docs.python-guide.org/writing/gotchas/) · Ruff B006

**Detected by:** Ruff B006 · custom `AST-MUT`

```python
# ✗ Never
def add_item(item, bucket=[]):
    bucket.append(item)
    return bucket  # same list every time!

# ✓ Always
def add_item(item, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
```

---

### bp-complexity — Keep functions simple

**Principle:** Cyclomatic complexity above 10 correlates strongly with defect density and makes
functions hard to reason about and test. Extract helpers and reduce branching.

**Citation:** McCabe, "A Complexity Measure" (1976) · Ruff C901

**Detected by:** Ruff C901 · custom `AST-CX`

---

### bp-context-managers — Use context managers for resource lifecycle

**Principle:** Files, DB connections, and locks must be closed/released even when exceptions occur.
Use `with` statements rather than manual `try/finally` cleanup — they are safer and shorter.

**Citation:** [PEP 343 — The `with` Statement](https://peps.python.org/pep-0343/)

```python
# ✗ Never
f = open("data.txt")
try:
    return f.read()
finally:
    f.close()

# ✓ Always
with open("data.txt") as f:
    return f.read()
```

---

### bp-swallow-exception — Don't silently swallow exceptions

**Principle:** `except: pass` discards every error with no trace, making failures invisible in
production. At minimum, log the exception with a meaningful message so failures are observable.

**Why it matters:** Silent failures create ghost bugs — the system appears to work but silently
produces wrong results. Observability starts with never losing error information.

**Citation:** Bandit B110 · [Google Python Style Guide — Exceptions](https://google.github.io/styleguide/pyguide.html#24-exceptions)

**Detected by:** Bandit S110

```python
# ✗ Never
try:
    send_email(user)
except Exception:
    pass  # no one knows this failed

# ✓ Always
try:
    send_email(user)
except Exception as exc:
    logger.error("Failed to send email to %s: %s", user.email, exc)
    raise  # or handle specifically
```

---

### bp-dead-code — Remove dead / unused code

**Principle:** Unused variables and imports add noise, can mask bugs (a variable shadowing a
real one), and mislead future maintainers. Delete them; ruff flags `F401` (unused import) and
`F841` (unused local variable).

**Citation:** Ruff Pyflakes rules (F401, F841) · Clean Code — Robert C. Martin

**Detected by:** Ruff F401, F841

```python
# ✗ Never
import os          # unused
from datetime import datetime  # unused

def process(data):
    result = transform(data)  # F841 — result never read
    return None

# ✓ Always — remove unused imports and variables
def process(data):
    return transform(data)
```

---

### bp-docstrings — Document public functions

**Principle:** Public functions, classes, and modules should have a docstring describing their
intent, parameters, and return value. Callers should not have to read the implementation to
understand how to use something.

**Citation:** [PEP 257 — Docstring Conventions](https://peps.python.org/pep-0257/)

```python
# ✗ Never — caller must read the body
def paginate(items, page, size):
    return items[page * size : (page + 1) * size]

# ✓ Always
def paginate(items, page, size):
    """Return a single page of items.

    Args:
        items: Sequence to paginate.
        page:  Zero-based page index.
        size:  Number of items per page.

    Returns:
        A slice of `items` for the requested page.
    """
    return items[page * size : (page + 1) * size]
```

---

### bp-type-hints — Add type hints to public APIs

**Principle:** Type hints catch whole classes of bugs via static analysis (`mypy`, `pyright`) and
document intent without prose. Annotate public function signatures; internal helpers can be
inferred.

**Citation:** [PEP 484 — Type Hints](https://peps.python.org/pep-0484/) · [Google Python Style Guide — Type Annotations](https://google.github.io/styleguide/pyguide.html#3194-decision)

```python
# ✗ No hints — callers don't know what types are expected
def create_token(user_id, expires_in):
    ...

# ✓ Annotated
from datetime import timedelta

def create_token(user_id: int, expires_in: timedelta) -> str:
    ...
```

---

### bp-magic-numbers — Replace magic numbers and strings with named constants

**Principle:** Unexplained literals (`3`, `86400`, `"admin"`) make intent opaque and create
maintenance traps when the value must change. Extract them as named constants at module level.

**Citation:** Clean Code — Robert C. Martin · [PEP 8 — Constants](https://peps.python.org/pep-0008/#constants)

```python
# ✗ Never
def is_token_expired(created_at):
    return (now() - created_at).seconds > 3600  # what is 3600?

# ✓ Always
TOKEN_TTL_SECONDS = 3600  # 1 hour

def is_token_expired(created_at):
    return (now() - created_at).seconds > TOKEN_TTL_SECONDS
```

---

### bp-long-functions — Keep functions short and focused

**Principle:** Functions longer than ~40–50 lines typically do more than one thing. Extract
cohesive sub-operations into well-named helper functions so each unit is independently readable
and testable.

**Citation:** Clean Code — Robert C. Martin · [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#383-functions-and-methods)

**Detected by:** custom `AST-LEN`

```python
# ✗ Never — 80-line function mixing DB, email, and audit logic
def register_user(form):
    # validate ...  (20 lines)
    # insert to DB ... (20 lines)
    # send welcome email ... (20 lines)
    # write audit log ... (20 lines)

# ✓ Extract cohesive steps
def register_user(form):
    user = _validate_and_create(form)
    _send_welcome_email(user)
    _audit_log("register", user)
    return user
```

---

### bp-deep-nesting — Avoid deep nesting

**Principle:** More than 3 levels of indentation (`if` / `for` / `try` / `with`) makes control
flow hard to reason about and test. Flatten using guard clauses, early return, and extraction.

**Citation:** Clean Code — Robert C. Martin · Refactoring — Martin Fowler

```python
# ✗ Never — 4+ levels deep
def process(data):
    if data:
        for item in data:
            if item.active:
                try:
                    result = transform(item)
                    ...

# ✓ Guard-clause + extraction
def process(data):
    if not data:
        return
    for item in data:
        _process_item(item)

def _process_item(item):
    if not item.active:
        return
    result = transform(item)
    ...
```

---

### bp-global-state — Avoid global mutable state

**Principle:** Module-level mutable variables are invisible dependencies that make functions
non-deterministic, hard to test, and prone to race conditions in threaded code. Pass state
explicitly or encapsulate it in a class.

**Citation:** Clean Architecture — Robert C. Martin · [Python docs — global statement](https://docs.python.org/3/reference/simple_stmts.html#the-global-statement)

```python
# ✗ Never
_cache = {}

def get_user(user_id):
    if user_id not in _cache:   # mutable global — not thread-safe
        _cache[user_id] = db.find(user_id)
    return _cache[user_id]

# ✓ Encapsulate in a class
class UserRepository:
    def __init__(self):
        self._cache: dict[int, User] = {}

    def get(self, user_id: int) -> User:
        if user_id not in self._cache:
            self._cache[user_id] = self._db.find(user_id)
        return self._cache[user_id]
```

---

### bp-early-return — Use guard clauses and early return

**Principle:** Validate preconditions at the top of a function and return / raise immediately.
This keeps the happy path un-indented and makes preconditions explicit rather than buried in
nested `else` blocks.

**Citation:** Refactoring — Martin Fowler (Replace Nested Conditional with Guard Clauses) · Clean Code — Robert C. Martin

```python
# ✗ Never — happy path deeply nested
def process_order(order):
    if order:
        if order.is_paid:
            if order.items:
                return fulfill(order)

# ✓ Guard clauses — linear, flat
def process_order(order):
    if not order:
        raise ValueError("order is required")
    if not order.is_paid:
        raise PaymentRequired(order.id)
    if not order.items:
        raise ValueError("order has no items")
    return fulfill(order)
```

---

### bp-immutability — Prefer immutable data structures

**Principle:** Mutable shared state is the most common source of concurrency bugs and unexpected
side effects. Prefer `frozenset`, `tuple`, `NamedTuple`, or frozen `dataclass`; copy-on-write
when mutation is genuinely needed.

**Citation:** Effective Java — Joshua Bloch · [Python docs — dataclasses.frozen](https://docs.python.org/3/library/dataclasses.html#frozen-instances)

```python
# ✗ Mutable — callers can silently mutate internal state
class Config:
    def __init__(self):
        self.flags = ["debug"]

cfg = Config()
cfg.flags.append("trace")  # mutates shared config!

# ✓ Frozen dataclass — mutation raises FrozenInstanceError
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    flags: tuple[str, ...] = ("debug",)
```

---

## Architecture & Design

| ID | Practice |
|----|----------|
| `bp-srp` | Single Responsibility Principle |
| `bp-dry` | Don't Repeat Yourself |
| `bp-dependency-injection` | Depend on abstractions, inject dependencies |
| `bp-open-closed` | Design for extension, not modification |
| `bp-separation-concerns` | Separate data, logic, and presentation |
| `bp-repository-pattern` | Use the Repository pattern for data access |
| `bp-config-externalization` | Externalize all configuration |
| `bp-error-boundaries` | Handle errors at appropriate boundaries |
| `bp-interface-design` | Design interfaces before implementation |

---

### bp-srp — Single Responsibility Principle

**Principle:** A module, class, or function should have one reason to change. When a unit does two
unrelated things, split it — each part becomes easier to test and replace independently.

**Citation:** Clean Architecture — Robert C. Martin · SOLID Principles

**Symptom:** A class that manages both the HTTP layer and the database access. A function that both
fetches data and formats a response.

---

### bp-dry — Don't Repeat Yourself

**Principle:** Every piece of knowledge must have a single, unambiguous, authoritative
representation in the system. When the same logic appears in two places, they will diverge.

**Citation:** The Pragmatic Programmer — Hunt & Thomas (1999)

---

### bp-dependency-injection — Depend on abstractions, inject dependencies

**Principle:** High-level modules should not construct their own low-level dependencies (DB
connections, HTTP clients, clocks). Inject them so the implementation is swappable and testable.

**Citation:** SOLID — Dependency Inversion Principle · Clean Architecture

```python
# ✗ Never — hard to test, hard to swap
class OrderService:
    def __init__(self):
        self.db = sqlite3.connect("prod.db")

# ✓ Always — inject the dependency
class OrderService:
    def __init__(self, db):
        self.db = db
```

---

### bp-config-externalization — Externalize all configuration

**Principle:** Port numbers, URLs, feature flags, and thresholds must not be baked into code. Load
from environment variables or a config file so deployments differ only in config, not code.

**Citation:** [12-Factor App — III. Config](https://12factor.net/config)

```python
# ✗ Never
DB_HOST = "prod-db.internal"
TIMEOUT = 30

# ✓ Always
DB_HOST = os.environ["DB_HOST"]
TIMEOUT = int(os.environ.get("TIMEOUT", "30"))
```

---

### bp-separation-concerns — Separate data access, business logic, and presentation

**Principle:** Mixing SQL queries with business rules in a view handler creates a tightly coupled
ball of mud. Separate layers so each can change independently and be tested in isolation.

**Citation:** Separation of Concerns — Dijkstra · Clean Architecture

**Layer model:**

```
HTTP / CLI layer     ← only handles request/response plumbing
Business logic layer ← rules, validation, orchestration
Repository layer     ← all DB / external storage calls
```

---

### bp-open-closed — Design for extension, not modification

**Principle:** Existing, tested code should not need to change to accommodate new behaviors.
Use polymorphism, the strategy pattern, or hook points so new cases extend rather than fork
existing logic.

**Why it matters:** Modifying existing code risks breaking what already works and requires
re-testing everything that depended on it. New cases that add, not change, are safe by
construction.

**Citation:** Open/Closed Principle — Bertrand Meyer · SOLID Principles · Clean Architecture — Robert C. Martin

```python
# ✗ Never — adding a new format requires modifying this function
def export(data, format):
    if format == "csv":
        return to_csv(data)
    elif format == "json":
        return to_json(data)
    # adding "parquet" means editing this function forever

# ✓ Extend without modifying — register new exporters
EXPORTERS = {
    "csv":  to_csv,
    "json": to_json,
}

def export(data, format):
    if format not in EXPORTERS:
        raise ValueError(f"Unknown format: {format}")
    return EXPORTERS[format](data)

# Adding parquet: EXPORTERS["parquet"] = to_parquet  — no existing code touched
```

---

### bp-repository-pattern — Use the Repository pattern for data access

**Principle:** Data access logic belongs in a dedicated repository layer, not scattered across
service or view code. Repositories abstract the storage mechanism so the business logic never
imports a DB driver directly, making storage swappable and testable.

**Citation:** Domain-Driven Design — Eric Evans · Patterns of Enterprise Application Architecture — Martin Fowler

```python
# ✗ Never — business logic directly queries DB
def get_active_users(db_conn):
    return db_conn.execute(
        "SELECT * FROM users WHERE active = 1"
    ).fetchall()

# ✓ Repository layer owns all DB access
class UserRepository:
    def __init__(self, db):
        self._db = db

    def find_active(self) -> list[User]:
        rows = self._db.execute("SELECT * FROM users WHERE active = 1")
        return [User.from_row(r) for r in rows]

# Service code depends on the repo, not the DB
class UserService:
    def __init__(self, repo: UserRepository):
        self._repo = repo
```

---

### bp-error-boundaries — Handle errors at appropriate boundaries

**Principle:** Propagate exceptions to the outermost layer that has enough context to handle them
meaningfully. Don't catch-and-ignore internally; don't let implementation exceptions (e.g.,
`sqlite3.IntegrityError`) leak across API or service boundaries.

**Citation:** Clean Code — Robert C. Martin · Domain-Driven Design — Eric Evans

```python
# ✗ Never — leaks DB implementation detail to the caller
def create_user(email):
    db.execute("INSERT INTO users (email) VALUES (?)", (email,))
    # sqlite3.IntegrityError propagates to the HTTP handler

# ✓ Translate at the boundary
class DuplicateEmailError(Exception):
    pass

def create_user(email):
    try:
        db.execute("INSERT INTO users (email) VALUES (?)", (email,))
    except sqlite3.IntegrityError:
        raise DuplicateEmailError(email)

# HTTP handler catches DuplicateEmailError → 409, not IntegrityError → 500
```

---

### bp-interface-design — Design interfaces before implementation

**Principle:** Define the contract (signature, behaviour, error modes) of a module before writing
its internals. This surfaces coupling early and drives a consumer-first API — if the interface is
awkward to use, the implementation is probably wrong.

**Why it matters:** Implementations written first tend to expose their internals. Starting from the
caller's perspective produces simpler, more stable APIs.

**Citation:** Interface Segregation Principle — SOLID · Test-Driven Development — Kent Beck · [Programming to an interface — GoF](https://en.wikipedia.org/wiki/Design_Patterns)

```python
# ✓ Write the test (interface) first — implementation follows the contract
def test_order_total_includes_tax():
    order = Order(items=[Item("widget", price=10.00)], tax_rate=0.1)
    assert order.total == 11.00  # interface defined before implementation

# Then implement Order to satisfy the test — not the other way around
```

---

## Testing

| ID | Practice |
|----|----------|
| `bp-tests` | Cover changed logic with tests |
| `bp-unit-test-public` | Test public interfaces, not private internals |
| `bp-aaa-pattern` | Structure tests with Arrange-Act-Assert |
| `bp-mock-at-boundaries` | Mock only at system boundaries |

---

### bp-tests — Cover changed logic with tests

**Principle:** New or modified behavior should ship with automated tests. Untested branches are the
most common source of regressions that reach production. Aim for meaningful coverage of business
logic paths, edge cases, and error conditions — not just the happy path.

**Why it matters:** Code that has no tests can be refactored in ways that silently change
behavior. Tests are the only mechanism that makes future changes safe.

**Citation:** Google Testing Blog · Working Effectively with Legacy Code — Michael Feathers (2004)

```python
# ✓ Cover the modified function — including error cases
def test_discount_applied_to_eligible_items():
    cart = Cart([Item("book", price=20, eligible=True)])
    assert cart.total(discount=0.1) == 18.0

def test_discount_not_applied_to_ineligible_items():
    cart = Cart([Item("food", price=20, eligible=False)])
    assert cart.total(discount=0.1) == 20.0

def test_empty_cart_total_is_zero():
    assert Cart([]).total(discount=0.1) == 0.0
```

---

### bp-unit-test-public — Test public interfaces, not private internals

**Principle:** Tests coupled to private methods break on every refactor, even when the observable
behaviour is unchanged. Write tests that verify behaviour through the public API — they survive
implementation changes and give refactoring confidence.

**Why it matters:** Private method tests create a 1:1 coupling between tests and implementation.
This doubles the cost of every refactor without improving correctness guarantees.

**Citation:** Test-Driven Development — Kent Beck · [Google Testing Blog — Don't test private methods](https://testing.googleblog.com/2008/12/testing-state-vs-testing-interaction.html)

```python
# ✗ Never — tests a private helper that might be inlined away
def test__normalize_email():
    svc = UserService()
    assert svc._normalize_email(" Alice@EXAMPLE.COM ") == "alice@example.com"

# ✓ Always — test via the public entry point
def test_register_normalizes_email():
    svc = UserService(repo=FakeRepo())
    user = svc.register(email=" Alice@EXAMPLE.COM ")
    assert user.email == "alice@example.com"
```

---

### bp-aaa-pattern — Arrange-Act-Assert

**Principle:** Each test sets up its context (Arrange), executes the unit under test (Act), and
verifies the outcome (Assert). One logical assertion per test keeps failures informative.

**Citation:** TDD by Example — Kent Beck · xUnit Patterns

```python
def test_add_item_initializes_bucket():
    # Arrange
    service = BucketService()
    # Act
    result = service.add_item("apple")
    # Assert
    assert result == ["apple"]
```

---

### bp-mock-at-boundaries — Mock only at system boundaries

**Principle:** Mock external services (HTTP, DB, clock, file system) but not internal classes.
Over-mocking creates tests that pass against incorrect implementations.

**Citation:** Growing Object-Oriented Software Guided by Tests — Freeman & Pryce (2009)

```python
# ✓ Correct boundary: mock the HTTP call, not internal helpers
@patch("myapp.clients.httpx.get")
def test_fetch_user(mock_get):
    mock_get.return_value = httpx.Response(200, json={"id": 1})
    user = fetch_user(user_id=1)
    assert user.id == 1
```

---

## Observability & Logging

| ID | Practice |
|----|----------|
| `bp-logging` | Use `logging`, not `print` |
| `bp-structured-logging` | Emit structured (JSON) logs in production |
| `bp-log-levels` | Use appropriate log levels |
| `bp-no-sensitive-logs` | Never log sensitive data |

---

### bp-logging — Use `logging`, not `print`

**Principle:** The `logging` module gives output a level, can be filtered per-module, and routed to
handlers (file, syslog, cloud aggregator) — all without code changes.

**Citation:** [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html)

```python
# ✗ Never
print(f"[DEBUG] Processing order {order_id}")

# ✓ Always
import logging
logger = logging.getLogger(__name__)
logger.debug("Processing order %s", order_id)
```

---

### bp-structured-logging — Emit structured logs in production

**Principle:** Structured (JSON) logs are parseable by aggregators (Datadog, ELK, Cloud Logging).
Include `request_id`, `user_id`, `duration_ms`, and `outcome` as fields, not embedded in
message strings.

**Citation:** [12-Factor App — XI. Logs](https://12factor.net/logs) · OpenTelemetry Logging spec

```python
# ✗ Hard to query
logger.info(f"User {user_id} purchased {item_id} in 142ms")

# ✓ Machine-readable
logger.info("purchase", extra={
    "user_id": user_id,
    "item_id": item_id,
    "duration_ms": 142,
    "outcome": "success",
})
```

---

### bp-log-levels — Use appropriate log levels

| Level | When |
|-------|------|
| `DEBUG` | Developer tracing (not emitted in production) |
| `INFO` | Normal operations — request completed, job started |
| `WARNING` | Recoverable anomaly — retry succeeded, config missing with a default |
| `ERROR` | Failure that needs attention — request failed, job crashed |
| `CRITICAL` | System-wide outage |

**Citation:** [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html) · Google SRE Book

---

## JavaScript / TypeScript

| ID | Practice | Tool |
|----|----------|------|
| `bp-js-strict-equality` | Use `===` (strict equality) | ESLint `eqeqeq` |
| `bp-js-no-var` | Use `const` / `let`, not `var` | ESLint `no-var` |
| `bp-promise-rejection` | Handle all Promise rejections | ESLint `@typescript-eslint/no-floating-promises` |
| `bp-ts-strict` | Enable TypeScript `strict` mode | `tsconfig.json` |

---

### bp-js-strict-equality — Use strict equality (`===`)

**Principle:** `==` in JavaScript performs implicit type coercion with results that surprise
everyone (`0 == '0'` is `true`; `null == undefined` is `true`). Use `===` / `!==` so
comparisons are type-safe by default.

**Citation:** [MDN — Equality comparisons](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Equality_comparisons_and_sameness) · Airbnb JS Style Guide

**Detected by:** ESLint `eqeqeq`

```js
// ✗ Never
if (userInput == 0) { ... }     // true for "", false, null, undefined, "0"

// ✓ Always
if (userInput === 0) { ... }    // true only when userInput is the number 0
```

---

### bp-js-no-var — Use `const` and `let` instead of `var`

**Principle:** `var` is function-scoped and hoisted — it is visible before its declaration and
leaks out of `if` / `for` blocks. `const` and `let` are block-scoped, making scope explicit and
preventing accidental re-use of loop variables.

**Citation:** [MDN — let](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/let) · [MDN — const](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/const) · ECMAScript 2015 (ES6) specification

**Detected by:** ESLint `no-var`

```js
// ✗ Never
for (var i = 0; i < 3; i++) { ... }
console.log(i); // 3 — leaks out of the loop!

// ✓ Always — let stays in the block
for (let i = 0; i < 3; i++) { ... }
// console.log(i) → ReferenceError outside the block

// Use const for values that won't be reassigned
const MAX_RETRIES = 3;
```

---

### bp-promise-rejection — Handle all Promise rejections

**Principle:** An unhandled Promise rejection crashes Node.js processes and silently swallows
errors in browsers. Every `Promise` chain must have a `.catch()` or be inside `async/await`
with a `try/catch`.

**Citation:** [MDN — Promise](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise) · Node.js `unhandledRejection` event

```js
// ✗ Never — rejection is silently lost
fetch(url).then(r => r.json()).then(process)

// ✓ Always
fetch(url)
  .then(r => r.json())
  .then(process)
  .catch(err => logger.error("fetch failed", err))

// or with async/await
try {
  const data = await fetch(url).then(r => r.json())
  process(data)
} catch (err) {
  logger.error("fetch failed", err)
}
```

---

### bp-ts-strict — Enable TypeScript strict mode

**Principle:** `"strict": true` in `tsconfig.json` enables `noImplicitAny`, `strictNullChecks`,
and several other checks that catch a large class of runtime errors at compile time. Start strict
on new projects; add it incrementally to existing ones.

**Citation:** [TypeScript Handbook — Strict mode](https://www.typescriptlang.org/tsconfig#strict) · Google TypeScript Style Guide

---

## API Design

| ID | Practice |
|----|----------|
| `bp-no-sensitive-response` | Never expose sensitive data in API responses |
| `bp-http-status-codes` | Return correct HTTP status codes |
| `bp-api-validation` | Validate all API inputs at the boundary |
| `bp-rate-limiting` | Rate-limit sensitive endpoints |
| `bp-csrf` | Protect state-changing endpoints against CSRF |

---

### bp-input-validation — Validate and sanitize external input

**Principle:** Treat all external input as untrusted. Validate type, range, format, and encoding at
the system boundary (HTTP request, CLI argument, file, env var) before any internal use.

**Why it matters:** Unchecked input is the root cause of injection attacks, buffer overflows,
and logic errors. Libraries like Pydantic, Zod, or Joi make boundary validation free.

**Citation:** [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)

```python
# ✗ Never — passes raw string into business logic
def create_user(email, age):
    db.insert("users", email=email, age=age)

# ✓ Always — validate at the boundary
class CreateUserRequest(BaseModel):
    email: EmailStr
    age: int = Field(..., ge=0, le=150)

def create_user(req: CreateUserRequest):
    db.insert("users", email=req.email, age=req.age)
```

---

### bp-path-traversal — Validate file paths against a trusted root

**Principle:** User-supplied paths must be resolved to their canonical form and checked to ensure
they remain inside an allowed root directory. A path like `../../etc/passwd` resolves outside the
intended directory.

**Why it matters:** Path traversal (CWE-22) allows attackers to read or overwrite arbitrary files
on the server, including config files, logs, and credentials.

**Citation:** [OWASP Path Traversal — CWE-22](https://owasp.org/www-community/attacks/Path_Traversal)

```python
# ✗ Never
def serve_file(filename):
    return open(f"/data/{filename}").read()  # ../../etc/passwd escapes /data/

# ✓ Always
from pathlib import Path

ROOT = Path("/data").resolve()

def serve_file(filename):
    path = (ROOT / filename).resolve()
    if not str(path).startswith(str(ROOT)):
        raise PermissionError("Path traversal detected")
    return path.read_text()
```

---

### bp-xss-docwrite — Avoid `document.write` with dynamic content

**Principle:** `document.write` can inject arbitrary HTML and JavaScript when its argument contains
unsanitized user data. Use DOM API methods (`createElement`, `appendChild`) instead, which treat
values as data rather than markup.

**Citation:** [OWASP DOM-based XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html)

**Detected by:** custom `SCAN-DOC-WRITE`

```js
// ✗ Never
document.write("<p>Hello " + userName + "</p>");  // XSS if userName is <script>...

// ✓ Always
const p = document.createElement("p");
p.textContent = "Hello " + userName;              // textContent never executes scripts
document.body.appendChild(p);
```

---

### bp-csrf — Protect state-changing endpoints against CSRF

**Principle:** POST / PUT / DELETE endpoints that change state must verify a CSRF token or enforce
`SameSite=Strict` (or `Lax`) cookies so cross-origin requests are rejected before any action is
taken.

**Why it matters:** Without CSRF protection a malicious page can trigger authenticated actions
(fund transfers, password changes) on behalf of a logged-in user just by loading an image or
submitting a form.

**Citation:** [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)

```python
# ✓ Flask-WTF — automatic CSRF token validation
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)

# ✓ Django — CSRF middleware enabled by default
# Disable only explicitly and with documented justification
```

---

### bp-least-privilege — Apply least-privilege access to resources

**Principle:** Services, DB connections, and file handles should request only the permissions they
need. A DB user that can only `SELECT` cannot be used to `DROP TABLE`. A process that only reads
files should not be granted write access.

**Why it matters:** When a component is compromised, blast radius is bounded by what that component
can access. Over-privileged credentials amplify every security incident.

**Citation:** [NIST AC-6 Least Privilege](https://csrc.nist.gov/projects/risk-management/sp800-53-controls/release-search#!/controls?version=5.1&family=AC) · [OWASP Access Control Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Access_Control_Cheat_Sheet.html)

```sql
-- ✗ Never — application user has full admin rights
GRANT ALL PRIVILEGES ON *.* TO 'app'@'%';

-- ✓ Always — grant only what the app needs
GRANT SELECT, INSERT, UPDATE ON app_db.* TO 'app_readonly'@'app-host';
```

---

### bp-auth-info-leak — Use generic error messages for authentication failures

**Principle:** Distinguish between "invalid password" and "account not found" only internally.
Return the same generic error message to the caller in both cases to prevent user enumeration.

**Why it matters:** Specific error messages let attackers identify valid usernames, which halves
the brute-force problem. Email confirmation flows are the most common source of this leak.

**Citation:** [OWASP Authentication Cheat Sheet — User Enumeration](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#authentication-and-error-messages)

```python
# ✗ Never — reveals whether the account exists
if not user:
    return "Account not found", 401
if not check_password(user, password):
    return "Wrong password", 401

# ✓ Always — same message for both failure modes
if not user or not check_password(user, password):
    return "Invalid credentials", 401
```

---

### bp-dependencies — Keep dependencies up to date and audited

**Principle:** Outdated dependencies are one of the leading sources of known vulnerabilities
(OWASP A06). Pin exact versions, run automated audits (`pip audit`, `npm audit`), and update
regularly. Review changelogs for breaking changes before upgrading.

**Why it matters:** Supply chain attacks increasingly target transitive dependencies. A pinned,
audited lockfile is the minimum baseline; automated PRs (Dependabot, Renovate) keep it low-effort.

**Citation:** [OWASP Top 10 — A06:2021 Vulnerable and Outdated Components](https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/)

```bash
# Python — audit installed packages
pip audit

# Node — audit installed packages
npm audit --audit-level=moderate

# CI — fail the build on high-severity findings
pip audit --strict
```

---

### bp-rate-limiting — Rate-limit sensitive endpoints

**Principle:** Login, password reset, and OTP endpoints must be rate-limited (token-bucket or
sliding-window) with per-IP and per-account limits to prevent brute-force and credential-stuffing
attacks.

**Why it matters:** Without rate limiting a 6-digit OTP can be exhausted in seconds. Credential
stuffing automation sends thousands of requests per minute against login endpoints.

**Citation:** [OWASP API Security — API4:2023 Unrestricted Resource Consumption](https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/) · [OWASP Credential Stuffing Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Credential_Stuffing_Prevention_Cheat_Sheet.html)

```python
# Flask-Limiter example
from flask_limiter import Limiter
limiter = Limiter(app, key_func=get_remote_address)

@app.route("/login", methods=["POST"])
@limiter.limit("10 per minute; 100 per hour")
def login():
    ...
```

---

### bp-no-sensitive-response — Never expose sensitive data in API responses

**Principle:** Password hashes, tokens, internal IDs, and stack traces must be stripped from
API responses. Serialize only the fields the client needs (allowlist / explicit DTO), not a
whole ORM object.

**Citation:** [OWASP API Security — API3:2023 Broken Object Property Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/)

```python
# ✗ Never — leaks password_hash, internal_id, ...
return user.__dict__

# ✓ Always
return {"id": user.public_id, "email": user.email, "name": user.name}
```

---

### bp-http-status-codes — Return correct HTTP status codes

**Principle:** HTTP status codes communicate semantics to clients and proxies. Returning `200 OK`
with an error body breaks monitoring, retries, and any client that reads the status code.

**Citation:** [RFC 9110 — HTTP Semantics](https://httpwg.org/specs/rfc9110.html)

| Situation | Code |
|-----------|------|
| Success | 200 OK |
| Resource created | 201 Created |
| Client error (bad input) | 400 Bad Request |
| Unauthenticated | 401 Unauthorized |
| Authenticated but forbidden | 403 Forbidden |
| Resource not found | 404 Not Found |
| Unhandled server error | 500 Internal Server Error |

---

### bp-api-validation — Validate all API inputs at the boundary

**Principle:** Validate schema, types, ranges, and required fields as the first step in every
endpoint handler — before any business logic or DB access. Use a schema library (Pydantic, Zod,
Joi) rather than manual if-chains.

**Citation:** [OWASP API Security — API1:2023](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)

```python
# ✓ FastAPI / Pydantic — validation is automatic
class CreateOrderRequest(BaseModel):
    item_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=1, le=100)

@app.post("/orders", status_code=201)
def create_order(body: CreateOrderRequest):
    ...  # body is already validated before reaching here
```

---

## Maintenance

**Adding a new practice**

1. Add the entry to `backend/corpus/best_practices.json` with a unique `"id"`.
2. Add the entry to this file under the right section.
3. Rebuild the index:
   ```bash
   python backend/corpus/build_index.py
   ```
4. The new practice is now cited in Scout reports and SKILL.md files automatically.

**Citation format:** Use the full source name so future readers can find it. Prefer:
- Standards / specs: `OWASP <name> · CWE-<n>`
- Books: `<Title> — <Author> (<year>)`
- RFCs / PEPs: `RFC <n> — <name>` / `PEP <n> — <name>`
- Tool docs: `<tool> <rule-code>`
