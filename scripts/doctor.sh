#!/bin/bash
# Check that the development environment is correctly set up.
# Run from any cwd — finds repo root automatically.

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    echo "FAIL: Not in a git repository"
    exit 1
fi

PY_DIR="$REPO_ROOT/packages/python"
PASS=0
FAIL=0

check() {
    if eval "$2" > /dev/null 2>&1; then
        echo "  ✓ $1"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $1"
        FAIL=$((FAIL + 1))
    fi
}

echo "Environment check for $(basename "$REPO_ROOT")"
echo "  Repo root: $REPO_ROOT"
echo ""

echo "Prerequisites:"
check "poetry available" "command -v poetry"
check "pnpm available" "command -v pnpm"
check "node available" "command -v node"
check "git available" "command -v git"

echo ""
echo "Python environment:"
check "packages/python exists" "test -d '$PY_DIR'"
check "pyproject.toml exists" "test -f '$PY_DIR/pyproject.toml'"
check "Poetry env exists" "cd '$PY_DIR' && poetry env info --path"
check "pytest installed" "cd '$PY_DIR' && poetry run pytest --version"
check "pyrightconfig.json exists" "test -f '$PY_DIR/pyrightconfig.json'"

echo ""
echo "Node environment:"
check "node_modules exists" "test -d '$REPO_ROOT/node_modules'"
check "pyright available" "cd '$PY_DIR' && npx pyright --version"

echo ""
echo "Canonical commands:"
check "pnpm test:py runnable" "cd '$REPO_ROOT' && pnpm run test:py -- --co -q"
check "pnpm typecheck:py runnable" "cd '$REPO_ROOT' && pnpm run typecheck:py"

echo ""
echo "Result: $PASS passed, $FAIL failed"
if [ $FAIL -gt 0 ]; then
    echo ""
    echo "Fix failures before proceeding. Common fixes:"
    echo "  pnpm install              # install node deps"
    echo "  cd packages/python && poetry install  # install python deps"
    exit 1
fi
