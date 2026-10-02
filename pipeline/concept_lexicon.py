"""Canonical concept vocabulary with aliases for chunk tagging."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConceptDefinition:
    """A teachable concept and its surface forms in text."""

    canonical: str
    aliases: tuple[str, ...] = ()
    phrases: tuple[str, ...] = ()
    domains: tuple[str, ...] = ("math", "physics", "cs", "problems")


# Curated STEM concepts — canonical name is the tag stored on chunks.
CONCEPT_LEXICON: list[ConceptDefinition] = [
    # --- Linear algebra ---
    ConceptDefinition("eigenvalues", ("eigenvalue", "eigenvalues"), (), ("math",)),
    ConceptDefinition("eigenvectors", ("eigenvector", "eigenvectors"), (), ("math",)),
    ConceptDefinition("matrices", ("matrix", "matrices"), (), ("math",)),
    ConceptDefinition("vectors", ("vector", "vectors"), (), ("math", "physics")),
    ConceptDefinition(
        "linear_transformations",
        ("linear transformation", "linear transformations"),
        ("linear map", "linear maps"),
        ("math",),
    ),
    ConceptDefinition(
        "determinants",
        ("determinant", "determinants", "det"),
        (),
        ("math",),
    ),
    ConceptDefinition(
        "orthogonality",
        ("orthogonal", "orthogonality", "perpendicular"),
        ("orthogonal matrix", "orthonormal"),
        ("math",),
    ),
    ConceptDefinition("subspaces", ("subspace", "subspaces"), (), ("math",)),
    ConceptDefinition(
        "matrix_decomposition",
        ("decomposition", "lu decomposition", "qr decomposition"),
        ("lu factorization", "qr factorization", "svd"),
        ("math",),
    ),
    ConceptDefinition("rank", ("rank",), ("column rank", "row rank"), ("math",)),
    ConceptDefinition(
        "gaussian_elimination",
        ("gaussian elimination", "row reduction"),
        ("elimination",),
        ("math",),
    ),
    # --- Mechanics ---
    ConceptDefinition("newtons_laws", ("newton", "newtons laws", "newton's laws"), (), ("physics",)),
    ConceptDefinition("forces", ("force", "forces"), (), ("physics",)),
    ConceptDefinition("momentum", ("momentum",), ("conservation of momentum",), ("physics",)),
    ConceptDefinition("energy", ("energy", "kinetic", "potential"), (), ("physics",)),
    ConceptDefinition(
        "kinematics",
        ("kinematics", "velocity", "acceleration"),
        ("one-dimensional kinematics",),
        ("physics",),
    ),
    ConceptDefinition("rotation", ("rotation", "rotational", "torque", "angular"), (), ("physics",)),
    ConceptDefinition("equilibrium", ("equilibrium", "static equilibrium"), (), ("physics",)),
    # --- Thermodynamics ---
    ConceptDefinition("entropy", ("entropy", "entropic"), (), ("physics",)),
    ConceptDefinition(
        "thermodynamics",
        ("thermodynamics", "thermodynamic"),
        ("laws of thermodynamics",),
        ("physics",),
    ),
    ConceptDefinition("temperature", ("temperature",), (), ("physics",)),
    ConceptDefinition("heat", ("heat", "calorimetry", "enthalpy"), (), ("physics",)),
    ConceptDefinition(
        "chemical_equilibrium",
        ("chemical equilibrium",),
        ("equilibrium constant",),
        ("physics",),
    ),
    ConceptDefinition(
        "phase_transitions",
        ("phase transition", "phase transitions"),
        ("clausius-clapeyron", "clausius clapeyron"),
        ("physics",),
    ),
    ConceptDefinition("ideal_gas", ("ideal gas",), ("equation of state",), ("physics",)),
    # --- Algorithms & CS ---
    ConceptDefinition(
        "algorithms",
        ("algorithm", "algorithms"),
        (),
        ("cs", "problems"),
    ),
    ConceptDefinition(
        "complexity_analysis",
        ("complexity", "big-o", "big o", "asymptotic"),
        ("time complexity", "space complexity", "theta", "big-o notation"),
        ("cs",),
    ),
    ConceptDefinition(
        "sorting",
        ("sort", "sorting", "sorted"),
        ("merge sort", "quicksort", "heapsort", "counting sort", "radix sort"),
        ("cs",),
    ),
    ConceptDefinition(
        "hashing",
        ("hash", "hashing", "hashtable", "hash table"),
        ("hash function", "chaining"),
        ("cs",),
    ),
    ConceptDefinition(
        "trees",
        ("tree", "trees", "binary tree"),
        ("avl tree", "avl trees", "binary search tree", "bst"),
        ("cs",),
    ),
    ConceptDefinition(
        "heaps",
        ("heap", "heaps", "priority queue"),
        ("binary heap",),
        ("cs",),
    ),
    ConceptDefinition(
        "graphs",
        ("graph", "graphs"),
        ("directed graph", "undirected graph"),
        ("cs",),
    ),
    ConceptDefinition(
        "breadth_first_search",
        ("bfs", "breadth-first search", "breadth first search"),
        (),
        ("cs",),
    ),
    ConceptDefinition(
        "depth_first_search",
        ("dfs", "depth-first search", "depth first search"),
        ("topological sort",),
        ("cs",),
    ),
    ConceptDefinition(
        "shortest_paths",
        ("shortest path", "shortest paths", "dijkstra", "bellman-ford"),
        ("weighted graph",),
        ("cs",),
    ),
    ConceptDefinition(
        "dynamic_programming",
        ("dynamic programming", "dp"),
        ("memoization", "optimal substructure"),
        ("cs",),
    ),
    ConceptDefinition(
        "divide_and_conquer",
        ("divide and conquer", "divide-and-conquer"),
        (),
        ("cs",),
    ),
    ConceptDefinition(
        "data_structures",
        ("data structure", "data structures"),
        ("dynamic array", "linked list"),
        ("cs",),
    ),
    ConceptDefinition(
        "recurrence_relations",
        ("recurrence", "recurrences", "recurrence relation"),
        (),
        ("cs", "math"),
    ),
]


def concepts_for_domain(domain: str) -> list[ConceptDefinition]:
    """Return lexicon entries applicable to a domain folder."""
    return [c for c in CONCEPT_LEXICON if domain in c.domains or not c.domains]


def all_canonical_concepts() -> list[str]:
    return [c.canonical for c in CONCEPT_LEXICON]
