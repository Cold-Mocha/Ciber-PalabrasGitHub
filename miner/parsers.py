# Utilidades para extraer nombres de funciones/métodos en Python y Java.

import ast
import javalang


def parse_python_functions(code_content: str) -> list[str]:
    """Extrae nombres de funciones y métodos de código Python usando AST"""
    function_names = []
    try:
        tree = ast.parse(code_content)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_names.append(node.name)
    except SyntaxError:
        pass
    return function_names


def parse_java_methods(code_content: str) -> list[str]:
    """Extrae nombres de métodos de código Java usando javalang"""
    method_names = []
    try:
        tree = javalang.parse.parse(code_content)
        for path, node in tree.filter(javalang.tree.MethodDeclaration):
            method_names.append(node.name)
    except (javalang.parser.JavaSyntaxError, Exception):
        pass
    return method_names