"""Validate the draft document and examples; this does not execute server scenarios."""
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate


def main():
    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root / "api/openapi.json").read_text(encoding="utf-8"))
    cases = json.loads((root / "contracts/sync-scenarios.json").read_text(encoding="utf-8"))
    validate(spec)
    refs = 0
    examples = 0

    def resolve(ref):
        if not ref.startswith("#/"):
            raise ValueError(f"External reference is not part of this draft: {ref}")
        value = spec
        for part in ref[2:].split("/"):
            value = value[part.replace("~1", "/").replace("~0", "~")]
        return value

    def expanded(value, ancestors=()):
        if isinstance(value, list):
            return [expanded(v, ancestors) for v in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            ref = value["$ref"]
            if ref in ancestors:
                raise ValueError("Example validator expects nonrecursive schemas")
            return expanded(resolve(ref), ancestors + (ref,))
        return {k: expanded(v, ancestors) for k, v in value.items()}

    def walk(value):
        nonlocal refs, examples
        if isinstance(value, dict):
            if "$ref" in value:
                resolve(value["$ref"])
                refs += 1
            if "schema" in value and "example" in value:
                Draft202012Validator(expanded(value["schema"]), format_checker=FormatChecker()).validate(value["example"])
                examples += 1
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(spec)
    operation_ids = []
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method not in {"get", "post", "put", "delete", "patch"}:
                continue
            operation_ids.append(operation["operationId"])
            declared = {p["name"] for p in item.get("parameters", []) + operation.get("parameters", []) if p.get("in") == "path"}
            if set(re.findall(r"\{([^}]+)\}", path)) != declared:
                raise ValueError(f"Missing/extraneous path parameter in {path}")
    if len(operation_ids) != len(set(operation_ids)):
        raise ValueError("Duplicate operationId")
    ids = [case["id"] for case in cases["scenarios"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate scenario ID")
    for case in cases["scenarios"]:
        if not case["given"] or not case["when"] or not case["then"]:
            raise ValueError(f"Incomplete scenario {case['id']}")
    print(f"PASS: OpenAPI 3.1, {len(operation_ids)} operations, {refs} internal references, {examples} schema-checked examples")
    print(f"PASS: {len(ids)} complete, uniquely named acceptance scenarios")
    print("Scenarios are specifications, not executed backend/security tests.")


if __name__ == "__main__":
    main()
