"""
State machine for MercadoLibre order lifecycle used by the pipeline.
Provides:
- States and allowed transitions
- Helpers to check transitions and list next states
- Renderers to print the full state machine (ASCII and Mermaid)
"""
from typing import Dict, List, Tuple

# Enumerate primary states we care about in the pipeline
STATES: List[str] = [
    "created",
    "paid",
    "ready_to_print",
    "printed",
    "shipped",
    "delivered",
    "canceled",
]

# Allowed transitions graph
# Note: this is conservative; adjust as business rules evolve
TRANSITIONS: Dict[str, List[str]] = {
    "created": ["paid", "canceled"],
    "paid": ["ready_to_print", "canceled"],
    "ready_to_print": ["printed", "canceled"],
    "printed": ["shipped", "canceled"],
    "shipped": ["delivered", "canceled"],
    "delivered": [],
    "canceled": [],
}

# Friendly labels (optional)
LABELS: Dict[str, str] = {
    "created": "Creada",
    "paid": "Pagada",
    "ready_to_print": "Lista para imprimir",
    "printed": "Impreso",
    "shipped": "Enviada",
    "delivered": "Entregada",
    "canceled": "Cancelada",
}


def can_transition(src: str, dst: str) -> bool:
    """Return True if a transition from src to dst is allowed."""
    return dst in TRANSITIONS.get(src, [])


def next_states(src: str) -> List[str]:
    """Return list of allowed next states from src."""
    return TRANSITIONS.get(src, [])


def all_transitions() -> List[Tuple[str, str]]:
    """Return list of all (src, dst) transitions."""
    pairs: List[Tuple[str, str]] = []
    for s, outs in TRANSITIONS.items():
        for d in outs:
            pairs.append((s, d))
    return pairs


def render_ascii() -> str:
    """Render a simple ASCII diagram of the state machine."""
    lines: List[str] = []
    lines.append("Estado → Posibles siguientes estados")
    lines.append("-" * 48)
    for s in STATES:
        outs = ", ".join(next_states(s)) or "(terminal)"
        lines.append(f"{s:<16} → {outs}")
    lines.append("")
    lines.append("Transiciones:")
    for src, dst in all_transitions():
        lines.append(f"  {src} -> {dst}")
    return "\n".join(lines)


def render_mermaid(direction: str = "LR") -> str:
    """Render Mermaid flowchart for documentation.

    Example to preview: copy this to a Mermaid renderer.
    """
    out: List[str] = []
    out.append(f"flowchart {direction}")
    for s in STATES:
        label = LABELS.get(s, s)
        out.append(f"  {s}([{label}])")
    for src, dst in all_transitions():
        out.append(f"  {src} --> {dst}")
    return "\n".join(out)


if __name__ == "__main__":
    # Quick manual preview
    print(render_ascii())
    print("\n--- Mermaid ---\n")
    print(render_mermaid())
