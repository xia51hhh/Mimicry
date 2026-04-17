"""Register DSL-related RPC methods."""
from ..rpc.methods import rpc_method
from .parser import parse
from .compiler import compile_to_json, decompile_from_json


@rpc_method("dsl.parse")
def dsl_parse(source: str = "") -> dict:
    """Parse pseudocode DSL and return workflow JSON."""
    workflow_ast = parse(source)
    return compile_to_json(workflow_ast)


@rpc_method("dsl.decompile")
def dsl_decompile(workflow: dict | None = None) -> str:
    """Convert workflow JSON back to pseudocode."""
    if not workflow:
        return ""
    return decompile_from_json(workflow)
