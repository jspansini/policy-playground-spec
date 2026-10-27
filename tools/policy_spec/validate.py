"""Validador do Policy Spec (design §7.1, task 3.1).

Uso:
    python tools/policy_spec/validate.py <arquivo>

Aceita o Policy Spec, o arquivo de extensions ou o dataset; os três são
procurados na mesma pasta. Sai com código 1 quando há erro bloqueante, para
que o Agent Hook mostre a falha ao agente. Só usa a biblioteca padrão.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_SECTIONS = ["policy", "stages", "rules", "variables", "parameters", "dag", "motivos", "validation_map", "output_vars"]
REQUIRED_RULE_FIELDS = ["id", "logic", "inputs", "outputs"]
KNOWN_LOGIC_TYPES = {"json_extract", "case_when", "matrix_lookup"}
POLICY_AREAS = {"Extraction", "ETL", "Hard filters", "Final base"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def find_files(path: Path) -> tuple[Path, Path | None]:
    folder = path.parent
    specs = [p for p in folder.glob("*.json") if not p.name.endswith(("-extensions.json", "-dataset.json"))]
    if path in specs:
        spec = path
    elif len(specs) == 1:
        spec = specs[0]
    else:
        raise SystemExit(f"Não encontrei um único Policy Spec em {folder}")
    ext = spec.with_name(spec.name.replace(".json", "-extensions.json")).name
    ext_path = folder / ext.replace("-policy-extensions", "-extensions")
    return spec, ext_path if ext_path.exists() else None


def validate_spec(spec: dict, rep: Report) -> None:
    for s in REQUIRED_SECTIONS:
        if s not in spec:
            rep.error(f"Seção obrigatória ausente: '{s}'")
    if not rep.ok:
        return

    rule_ids = {r.get("id") for r in spec["rules"]}
    param_ids = {p["id"] for p in spec["parameters"]}
    stage_ids = {s["id"] for s in spec["stages"]}

    for r in spec["rules"]:
        rid = r.get("id", "?")
        for f in REQUIRED_RULE_FIELDS:
            if f not in r:
                rep.error(f"Regra {rid}: campo obrigatório ausente '{f}'")
        ltype = r.get("logic", {}).get("type")
        if ltype not in KNOWN_LOGIC_TYPES:
            rep.error(f"Regra {rid}: logic.type '{ltype}' não suportado (esperado: {sorted(KNOWN_LOGIC_TYPES)})")
        for d in r.get("depends_on", []):
            if d not in rule_ids:
                rep.error(f"Regra {rid}: depends_on aponta para regra inexistente '{d}'")
        for p in r.get("parameters", []):
            if p not in param_ids:
                rep.error(f"Regra {rid}: parâmetro inexistente '{p}'")
        if r.get("stage_id") and r["stage_id"] not in stage_ids:
            rep.error(f"Regra {rid}: stage_id inexistente '{r['stage_id']}'")

    for v in spec["variables"]:
        pb = v.get("produced_by")
        if pb not in rule_ids and pb != "external":
            rep.error(f"Variável {v.get('name')}: produced_by '{pb}' não é regra nem 'external'")
    for p in spec["parameters"]:
        for u in p.get("used_by", []):
            if u not in rule_ids:
                rep.error(f"Parâmetro {p['id']}: used_by aponta para regra inexistente '{u}'")
    for m in spec["motivos"]:
        if m.get("rule_id") not in rule_ids:
            rep.error(f"Motivo {m.get('code')}: rule_id inexistente '{m.get('rule_id')}'")

    deps = {r["id"]: list(r.get("depends_on", [])) for r in spec["rules"] if "id" in r}
    cycle = find_cycle(deps)
    if cycle:
        rep.error("Ciclo no DAG: " + " → ".join(cycle))

    layer_of: dict[str, int] = {}
    for i, layer in enumerate(spec["dag"].get("execution_order", [])):
        for rid in layer:
            if rid not in rule_ids:
                rep.error(f"dag.execution_order cita regra inexistente '{rid}'")
            layer_of[rid] = i
    for rid in rule_ids - set(layer_of):
        rep.error(f"Regra {rid} não aparece em dag.execution_order")
    for rid, ds in deps.items():
        for d in ds:
            if rid in layer_of and d in layer_of and layer_of[d] >= layer_of[rid]:
                rep.error(f"Ordem inválida: {rid} (camada {layer_of[rid] + 1}) depende de {d} (camada {layer_of[d] + 1})")


def find_cycle(deps: dict[str, list[str]]) -> list[str] | None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in deps}
    stack: list[str] = []

    def visit(n: str) -> list[str] | None:
        color[n] = GRAY
        stack.append(n)
        for m in deps.get(n, []):
            if color.get(m) == GRAY:
                return stack[stack.index(m):] + [m]
            if color.get(m) == WHITE:
                found = visit(m)
                if found:
                    return found
        stack.pop()
        color[n] = BLACK
        return None

    for n in deps:
        if color[n] == WHITE:
            found = visit(n)
            if found:
                return found
    return None


def validate_extensions(spec: dict, ext: dict, folder: Path, rep: Report) -> None:
    ex = ext.get("extends", {})
    if ex.get("policy_id") != spec["policy"]["id"]:
        rep.error(f"Extensions: policy_id '{ex.get('policy_id')}' difere do Policy Spec '{spec['policy']['id']}'")
    if ex.get("source_commit") != spec["policy"].get("source_commit"):
        rep.error(f"Extensions: source_commit '{ex.get('source_commit')}' difere do Policy Spec '{spec['policy'].get('source_commit')}'")
    stage_ids = {s["id"] for s in spec["stages"]}
    for sid, area in ext.get("stage_area", {}).items():
        if sid not in stage_ids:
            rep.error(f"Extensions: estágio inexistente '{sid}' em stage_area")
        elif area not in POLICY_AREAS:
            rep.warn(f"Extensions: área da política desconhecida '{area}' no estágio {sid}")
    for sid in stage_ids - set(ext.get("stage_area", {})):
        rep.warn(f"Estágio {sid} sem área da política informada")
    params = {p["id"]: p for p in spec["parameters"]}
    for pid, dom in ext.get("parameter_domains", {}).items():
        if pid not in params:
            rep.error(f"Extensions: parâmetro inexistente '{pid}' em parameter_domains")
            continue
        v = params[pid].get("value")
        if isinstance(v, (int, float)) and not (dom.get("min", v) <= v <= dom.get("max", v)):
            rep.error(f"Parâmetro {pid}: valor de baseline {v} fora do domínio [{dom.get('min')}, {dom.get('max')}]")
    for ds in ext.get("datasets", []):
        f = folder / ds.get("file", "")
        if not f.exists():
            rep.error(f"Dataset {ds.get('dataset_version')}: arquivo '{ds.get('file')}' não existe (bloqueia só a execução)")
            continue
        if ds.get("contains_pii") is not False:
            rep.error(f"Dataset {ds.get('dataset_version')}: contains_pii precisa ser false (R15.5)")
        n = len(json.loads(f.read_text(encoding="utf-8")).get("records", []))
        if n != ds.get("record_count"):
            rep.error(f"Dataset {ds.get('dataset_version')}: record_count {ds.get('record_count')} mas o arquivo tem {n}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    spec_path, ext_path = find_files(Path(argv[1]).resolve())
    rep = Report()
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"✗ {spec_path.name}: JSON inválido ({e})")
        return 1
    validate_spec(spec, rep)
    if ext_path and rep.ok:
        validate_extensions(spec, json.loads(ext_path.read_text(encoding="utf-8")), spec_path.parent, rep)
    elif not ext_path:
        rep.warn("Arquivo de extensions não encontrado: parâmetros ficam somente leitura")

    print(f"Policy Spec: {spec_path.name}" + (f" + {ext_path.name}" if ext_path else ""))
    for w in rep.warnings:
        print(f"  ⚠ {w}")
    for e in rep.errors:
        print(f"  ✗ {e}")
    if rep.ok:
        print(f"✓ Válido: {len(spec['rules'])} regras, {len(spec['parameters'])} parâmetros, DAG sem ciclos")
        return 0
    print(f"✗ {len(rep.errors)} erro(s) bloqueante(s): exploração e investigação ficam bloqueadas (R16.2)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
