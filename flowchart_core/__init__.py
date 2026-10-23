from .models import (
    Connection, ConnectionType, Element, ElementType, Flowchart, Project,
)
from .symbols import SymbolTable
from .policy import CodePolicy, PolicyViolation
from .validator import CodeValidator, ValidationResult, validate_identifier
from .events import EventKind, ExecutionEvent
from .extensions import (
    ElementExtension, ElementMeta, ExtensionRegistry, FieldSpec, collect_declarations,
)
from .concurrency import register_builtins as register_concurrency_builtins
from .plan import ExecutionPlan, compile_plan
from .executor import FlowchartExecutor
from .codegen import CodeGenerator
from .languages import (
    LanguageBackend, LanguageRegistry, PythonBackend, JavaScriptBackend,
    get_language, language_display_names, language_registry, list_languages,
    register_language,
)
from .serialization import load_project, save_project
from .history import History
from .snippets import Snippet, SnippetLibrary
from .diagnostics import Diagnostic, analyze, format_diagnostics
from .completion import CompletionItem, CompletionProvider
from .module_inspector import (
    CallableInfo, get_callable_info, list_module_callables,
    list_installed_distributions,
)
from . import pypi_client


def create_default_registry(extension_dir: str | None = None) -> ExtensionRegistry:
    registry = ExtensionRegistry()
    register_concurrency_builtins(registry)
    if extension_dir:
        registry.load_directory(extension_dir)
    return registry


__all__ = [
    "Connection", "ConnectionType", "Element", "ElementType", "Flowchart", "Project",
    "SymbolTable", "CodePolicy", "PolicyViolation", "CodeValidator", "ValidationResult",
    "validate_identifier", "EventKind", "ExecutionEvent", "ElementExtension",
    "ElementMeta", "ExtensionRegistry", "FieldSpec", "collect_declarations",
    "register_concurrency_builtins", "ExecutionPlan", "compile_plan",
    "FlowchartExecutor", "CodeGenerator", "load_project", "save_project", "History",
    "Snippet", "SnippetLibrary", "Diagnostic", "analyze", "format_diagnostics",
    "CompletionItem", "CompletionProvider", "CallableInfo", "get_callable_info",
    "list_module_callables", "list_installed_distributions", "pypi_client",
    "create_default_registry",
    "LanguageBackend", "LanguageRegistry", "PythonBackend", "JavaScriptBackend",
    "get_language", "list_languages", "language_display_names",
    "language_registry", "register_language",
]
