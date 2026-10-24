"""Проверка синтаксиса JavaScript-файлов статики через tree-sitter.

Запуск из корня репозитория:

    python scripts/check_js.py            # проверяет static/js/*.js
    python scripts/check_js.py файл.js    # проверяет указанные файлы

Выходит с кодом 1, если в каком-либо файле найден узел ERROR (синтаксическая
ошибка) или MISSING (пропущенный токен, например закрывающая скобка). Это проверка
разбора, а не линтер: стиль и ошибки времени выполнения она не ищет.
"""

import sys
from pathlib import Path

import tree_sitter_javascript
from tree_sitter import Language, Parser

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATTERN = "static/js/*.js"


def _parser():
    return Parser(Language(tree_sitter_javascript.language()))


def _problem_nodes(root):
    """Возвращает узлы ERROR и MISSING. Поддеревья без ошибок пропускаются по has_error."""
    stack = [root]
    while stack:
        node = stack.pop()
        if not node.has_error:
            continue
        if node.type == "ERROR" or node.is_missing:
            yield node
        stack.extend(node.children)


def check_file(path, parser):
    """Возвращает список найденных проблем в виде строк «путь:строка:столбец: ...»."""
    tree = parser.parse(path.read_bytes())
    problems = []
    for node in _problem_nodes(tree.root_node):
        line, column = node.start_point
        description = f"MISSING {node.type}" if node.is_missing else "ERROR"
        problems.append(f"{path}:{line + 1}:{column + 1}: {description}")
    return problems


def main(argv):
    paths = [Path(arg) for arg in argv] if argv else sorted(ROOT.glob(DEFAULT_PATTERN))
    if not paths:
        print("Не найдено ни одного JavaScript-файла для проверки", file=sys.stderr)
        return 1
    missing = [path for path in paths if not path.is_file()]
    if missing:
        for path in missing:
            print(f"Файл не найден: {path}", file=sys.stderr)
        return 1
    parser = _parser()
    problems = []
    for path in paths:
        problems.extend(check_file(path, parser))
    for problem in problems:
        print(problem, file=sys.stderr)
    checked = len(paths)
    if problems:
        print(f"Синтаксических проблем: {len(problems)} (файлов проверено: {checked})", file=sys.stderr)
        return 1
    print(f"JavaScript: синтаксических ошибок нет (файлов проверено: {checked})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
