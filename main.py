from __future__ import annotations

import functools
import os
import re
import sys
from typing import Dict, Set, Optional, List


class Node:
    def __init__(self, namespace: str):
        self.__path: Optional[str] = None
        self.__namespace: str = namespace
        self.__dependents: Set[Node] = set()

    def get_namespace(self) -> str:
        return self.__namespace

    def get_basename(self) -> str:
        return self.__namespace.split('\\')[-1]

    def has_path(self) -> bool:
        return self.__path is not None

    def get_path(self) -> Optional[str]:
        return self.__path

    def set_path(self, path: str) -> None:
        self.__path = path

    def get_dependents(self) -> Set[Node]:
        return self.__dependents

    def add_dependent(self, node: Node) -> None:
        self.__dependents.add(node)


def convert_linefeed_to_space(s: str) -> str:
    return s.replace('\n', ' ')


def trim_continuous_space(s: str) -> str:
    return re.sub(' +', ' ', s)


REGEX_LABEL_CHARS = r'[a-zA-Z_\x7f-\xff][a-zA-Z0-9_\x7f-\xff]*'
REGEX_LABEL_CHARS_FIRST_UPPER = r'[A-Z_\x7f-\xff][a-zA-Z0-9_\x7f-\xff]*'
REGEX_NAMESPACE = r'[a-zA-Z_\x7f-\xff\\][a-zA-Z0-9_\x7f-\xff\\]*'
REGEX_NAMESPACE_FIRST_UPPER = r'[A-Z_\x7f-\xff\\][a-zA-Z0-9_\x7f-\xff\\]*'

REGEX_CLASS_DECLARATION = rf'(?:class|interface|trait) {REGEX_LABEL_CHARS}'
REGEX_NAMESPACE_STMT = rf'namespace {REGEX_NAMESPACE};'
REGEX_USE_STMT = rf'use {REGEX_NAMESPACE_FIRST_UPPER};'
REGEX_NEW_STMT = rf'new {REGEX_LABEL_CHARS}'
REGEX_STATIC_CALL = rf'{REGEX_NAMESPACE_FIRST_UPPER}::'
REGEX_VAR_TYPE_HINT = rf' *{REGEX_LABEL_CHARS_FIRST_UPPER} \${REGEX_LABEL_CHARS}'

re_class_declaration = re.compile(REGEX_CLASS_DECLARATION)
re_namespace_stmt = re.compile(REGEX_NAMESPACE_STMT)
re_use_stmt = re.compile(REGEX_USE_STMT)
re_new_stmt = re.compile(REGEX_NEW_STMT)
re_static_call = re.compile(REGEX_STATIC_CALL)
re_var_type_hint = re.compile(REGEX_VAR_TYPE_HINT)


def visit_dependents_of(node: Node):
    print(f'class "{node.get_basename()}" {{}}')
    if len(node.get_dependents()) == 0:
        return
    for dependent in node.get_dependents():
        print(f'"{dependent.get_basename()}" --> "{node.get_basename()}"')
        visit_dependents_of(dependent)


def main():
    target_dirs: List[str] = sys.argv[1:-1]
    target_fqcn: str = sys.argv[-1]

    # ノードの一覧
    fqcn_to_node: Dict[str, Node] = {}
    namespace_to_node: Dict[str, Node] = {}

    for d in target_dirs:
        for cur_dir, _, filenames in os.walk(d):
            for i, filename in enumerate([f for f in filenames if f.endswith('.php')]):

                src_path = cur_dir + '/' + filename
                class_name_from_file = filename.removesuffix('.php')

                with open(src_path, 'r') as f:

                    # ファイル内容を読み込む
                    lines = f.readlines()
                    file_content = ''.join(lines)
                    # ファイルを解析しやすい形式にフォーマットする
                    formatted_file_content = functools.reduce(
                        lambda f, g: lambda *x: g(f(*x)),
                        [
                            convert_linefeed_to_space,
                            trim_continuous_space
                        ]
                    )(file_content)

                    # 完全修飾クラス名を抽出
                    namespace_search = re_namespace_stmt.findall(formatted_file_content)
                    namespace = namespace_search[0].removeprefix('namespace ').removesuffix(';') if len(namespace_search) == 1 else ''
                    class_name_search = re_class_declaration.findall(formatted_file_content)
                    class_name = class_name_search[0].removeprefix('class ').removeprefix('interface ').removeprefix('trait ') if len(class_name_search) == 1 else ''
                    fully_qualified_class_name = '\\'.join([namespace, class_name])

                    # use しているクラスを抽出
                    use_stmt_search = re_use_stmt.findall(formatted_file_content)
                    use_list = list({res.removeprefix('use ').removesuffix(';'): True for res in use_stmt_search}.keys())

                    # new しているクラスを抽出
                    new_stmt_search = re_new_stmt.findall(formatted_file_content)
                    new_list = list({res.removeprefix('new '): True for res in new_stmt_search}.keys())

                    # 静的呼び出ししているクラスを抽出
                    static_call_search = re_static_call.findall(formatted_file_content)
                    static_call_list = list({res.removesuffix('::'): True for res in static_call_search}.keys())

                    # 変数への型ヒントのクラスを抽出
                    var_type_hint_search = re_var_type_hint.findall(formatted_file_content)
                    var_type_hint_list = list({res.removeprefix(' ').split(' $')[0]: True for res in var_type_hint_search}.keys())

                    if fully_qualified_class_name not in fqcn_to_node:
                        fqcn_to_node[fully_qualified_class_name] = Node(fully_qualified_class_name)
                    fqcn_to_node[fully_qualified_class_name].set_path(src_path)

                    for use in use_list:
                        if use not in fqcn_to_node:
                            fqcn_to_node[use] = Node(use)
                        fqcn_to_node[use].add_dependent(fqcn_to_node[fully_qualified_class_name])

    target_node = fqcn_to_node[target_fqcn]
    print('@startuml')
    visit_dependents_of(target_node)
    print('@enduml')


if __name__ == '__main__':
    main()
