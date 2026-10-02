#!/bin/bash

cd "$(dirname "$0")/.."

FAILED=0

run_test() {
    local title="$1" expected="$2"
    shift 2
    echo "=== $title ==="
    echo "exit" | ./run.sh "$@"
    local code=$?
    if [ "$code" -eq "$expected" ]; then
        echo ">>> OK (код возврата $code)"
    else
        echo ">>> ОШИБКА: ожидался код $expected, получен $code"
        FAILED=$((FAILED + 1))
    fi
    echo
}

run_test "1. Только --vfs" 0 --vfs ./vfs/test.csv
run_test "2. --vfs и --script" 0 --vfs ./vfs/test.csv --script tests/start.emu
run_test "3. Несуществующий скрипт (ошибка сообщается, эмулятор работает дальше)" 0 \
    --vfs ./vfs/test.csv --script tests/no_such.emu
run_test "4. Без обязательного --vfs (ожидается ошибка параметров)" 2 \
    --script tests/start.emu

echo "=============================="
if [ "$FAILED" -eq 0 ]; then
    echo "ИТОГ: ошибок нет, все тесты пройдены"
    exit 0
else
    echo "ИТОГ: тестов с ошибками: $FAILED"
    exit 1
fi