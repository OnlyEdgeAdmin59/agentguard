"""Opciones de línea de comandos de --deep y el aviso de privacidad antes de enviar."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from . import deep
from .i18n import get_lang, t

FLAGS_WITH_VALUE = ("--deep-provider", "--deep-model", "--deep-fail-on")
FLAGS = ("--deep", "--deep-yes", "--deep-dry-run")


@dataclass
class DeepOpts:
    enabled: bool = False
    provider: str = deep.DEFAULT_PROVIDER
    model: str = ""
    yes: bool = False
    dry_run: bool = False
    fail_on_high: bool = False


def pop_deep(argv: list[str]) -> tuple[DeepOpts, list[str]] | str:
    """Saca las opciones --deep* de argv. Devuelve un mensaje de error si algo está mal."""
    opts, rest, i = DeepOpts(), [], 0
    while i < len(argv):
        a = argv[i]
        if a in FLAGS_WITH_VALUE:
            if i + 1 >= len(argv):
                return t("Falta el valor de {flag}", flag=a)
            value = argv[i + 1]
            if a == "--deep-provider":
                opts.provider = value
            elif a == "--deep-model":
                opts.model = value
            elif value.lower() in ("high", "alto"):
                opts.fail_on_high = True
            else:
                return t("--deep-fail-on solo acepta: high")
            i += 2
            continue
        if a == "--deep":
            opts.enabled = True
        elif a == "--deep-yes":
            opts.yes = True
        elif a == "--deep-dry-run":
            opts.dry_run = True
        else:
            rest.append(a)
        i += 1
    used_extra = opts.yes or opts.dry_run or opts.fail_on_high or opts.model or opts.provider != deep.DEFAULT_PROVIDER
    if used_extra and not opts.enabled:
        return t("Las opciones --deep-* necesitan --deep")
    if opts.provider not in ("anthropic", "ollama"):
        return t("Proveedor desconocido: {p} (usa anthropic u ollama)", p=opts.provider)
    if opts.provider == "ollama" and not opts.model:
        return t("Con --deep-provider ollama hay que indicar el modelo: --deep-model <nombre>")
    opts.model = opts.model or deep.DEFAULT_MODEL
    return opts, rest


def _confirm(prompt: str) -> bool:
    try:
        answer = input(prompt)
    except EOFError:
        return False
    return answer.strip().lower() in ("s", "si", "sí", "y", "yes")


def session(files: list[Path], opts: DeepOpts, transport: deep.Transport | None = None,
            interactive: bool | None = None) -> tuple[list, deep.Stats] | int:
    """Avisa qué se envía y a dónde, pide confirmación y corre el juez.

    Devuelve (hallazgos, stats), o un código de salida si no se envió nada.
    """
    units = [u for p in files for u in deep.units_from_file(p)]
    size_kb = sum(len(u.text.encode("utf-8")) for u in units) / 1024
    tokens, cost = deep.estimate(units, opts.model)
    cost_txt = "~" + deep.money(cost) if cost is not None else t("desconocido")
    if opts.provider == "anthropic":
        print(t("--deep enviará {n} elemento(s) de {files} archivo(s) ({kb:.0f} KB, ~{tokens} tokens) a {host} "
                "(modelo {model}). Costo estimado: {cost}. Antes de enviar se tapan las claves que parezcan reales.",
                n=len(units), files=len(files), kb=size_kb, tokens=tokens, host=deep.ANTHROPIC_HOST,
                model=opts.model, cost=cost_txt))
    else:
        print(t("--deep juzgará {n} elemento(s) con Ollama en {host} (modelo {model}). No sale nada de esta máquina.",
                n=len(units), host=deep.OLLAMA_HOST, model=opts.model))
    if opts.dry_run:
        for u in units:
            print(f"  {u.source} ({len(u.text)} {t('caracteres')})")
        print(t("--deep-dry-run: no se envió nada."))
        return 0
    if not units:
        return [], deep.Stats(model=opts.model)
    if opts.provider == "anthropic" and not opts.yes:
        interactive = sys.stdin.isatty() if interactive is None else interactive
        if not interactive:
            print(t("Sin terminal interactiva no se envía nada. Agrega --deep-yes para confirmar."))
            return 2
        if not _confirm(t("¿Continuar? [s/N] ")):
            print(t("Cancelado: no se envió nada."))
            return 2
    try:
        transport = transport or deep.make_transport(opts.provider, opts.model)
        findings, stats = deep.run(units, transport, get_lang(), opts.model)
    except deep.DeepError as e:
        print(t("--deep no pudo correr: {err}", err=str(e)))
        return 2
    return findings, stats


def summary(findings: list, stats: deep.Stats) -> str:
    cost = stats.cost()
    cost_txt = deep.money(cost) if cost is not None else t("desconocido")
    high = sum(f.level == "ALTO" for f in findings)
    text = t("deep ({model}): {calls} llamada(s), {findings} hallazgo(s), {high} ALTO(s), {none} sin veredicto. "
             "Tokens {tin}/{tout}, costo {cost}.", model=stats.model, calls=stats.calls,
             findings=sum(f.rule == deep.RULE_DEEP for f in findings), high=high, none=stats.no_verdict,
             tin=stats.input_tokens, tout=stats.output_tokens, cost=cost_txt)
    if stats.redacted:
        text += " " + t("Se taparon {n} secreto(s) antes de enviar.", n=stats.redacted)
    return text
