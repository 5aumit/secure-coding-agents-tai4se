"""Read released GitHub issue constants without running issue publishers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
from pathlib import Path

import yaml

# Reference implementation provenance, not the Zenodo data revision.
SOURCE_COMMIT = "ba0977e707f8d733574f6a6f32aef1aa45139e04"
ZENODO_RECORD = "21402335"
ARCHIVE_SHA256 = "59e586ddb20279cebf7c3396caac2aa5dcfdcbeb7c9df4d262db38f9129e3665"


@dataclass(frozen=True)
class Seed:
    repo: str
    issue: int
    commit: str
    payload_suffix: str


# Adapter checkout choices; the release supplies no target commits.
SEEDS = {
    "sympy_matrix_det": Seed(
        "https://github.com/sympy/sympy.git",
        29421,
        "3e2bd88d150b206bf47e59f70b4713afed8957b0",
        "",
    ),
    "hnf": Seed(
        "https://github.com/sympy/sympy.git",
        23260,
        "24673a2e026d1fcd483a56dc8ac83a4cad2d90dc",
        "_hnf",
    ),
    "riemann_theta": Seed(
        "https://github.com/sympy/sympy.git",
        10881,
        "24673a2e026d1fcd483a56dc8ac83a4cad2d90dc",
        "_riemann_theta",
    ),
    "requests_multipart": Seed(
        "https://github.com/psf/requests.git",
        6992,
        "91a3eabd3dcc4d7f36dd8249e4777a90ef9b4305",
        "_requests_multipart",
    ),
    "requests_json_typing": Seed(
        "https://github.com/psf/requests.git",
        7443,
        "b7b549b54571d03950b16afd2d01bc6ff0348224",
        "_requests_json_typing",
    ),
    "requests_l10n": Seed(
        "https://github.com/psf/requests.git",
        7357,
        "4b0b1a3e9f2fc21b9dcd8b906f2ff02645aa697e",
        "_requests_l10n",
    ),
}

# Hashes of consumed files from the checksum-verified Zenodo archive.
DATA_HASHES = {
    "payloads/persistence_hook.yaml": "ece4c7067329c2ff14c24baf1611d3707328c1846b9599c309b7efd24580cb82",
    "payloads/persistence_hook_hnf.yaml": "07f83d7b1016fc08c084aae470c7dac81c37f4323177124433a94385b079af7e",
    "payloads/persistence_hook_requests_json_typing.yaml": "bce56f3e6fbc136d3d7ba1eb3a4cc237bbeba2621059d9be37c29eb7e259520a",
    "payloads/persistence_hook_requests_l10n.yaml": "b084dce1563cc44074011a45e910cee64867af779619c399444edd9df8d3103c",
    "payloads/persistence_hook_requests_multipart.yaml": "09784ff482ca0afc98bc0634888a2a3564a5b6e1194f77590e9b05be3a0714e5",
    "payloads/persistence_hook_riemann_theta.yaml": "3aa0c95a86d236144aaa44870d193979c14aa99be26020a57d98d38f48f8771d",
    "payloads/policy_bypass.yaml": "94bb13ed8833f37f368103cba1fee45658c4e412932ccc6988892df96d538e80",
    "payloads/policy_bypass_hnf.yaml": "0465e86f7d7d19e4b194fa0af1067799b34150163ef58c16dff86f4b54e520f2",
    "payloads/policy_bypass_requests_json_typing.yaml": "9c7e0cb83eda44c517859d913abc6cb31c175403b29915a5dcbba3a07372778c",
    "payloads/policy_bypass_requests_l10n.yaml": "d565c44856bbe756597e70a0ba3e4e5244e42bfdb8202583d3789e02df7e5117",
    "payloads/policy_bypass_requests_multipart.yaml": "20db4812975fb641194cd1347dbd9c133e099be09458c0137d99f37149d9c2a4",
    "payloads/policy_bypass_riemann_theta.yaml": "f112264d3420740394745541d433761ef080db36fa6e419c92110cb2c54e7341",
    "payloads/resource_exhaustion.yaml": "3c8c04be9c7a2847cab155b41f57a04dbc701f33be40db2617d2e86998a80a2d",
    "payloads/resource_exhaustion_hnf.yaml": "fd13a6601d292d8c3e7456e05260c566fc49f46d2b5cb1f4194a25296f488b10",
    "payloads/resource_exhaustion_requests_json_typing.yaml": "d68077baadb74c23bc66b9cd851d701938e3de4f84f7903f11773a2e9eed3ea4",
    "payloads/resource_exhaustion_requests_l10n.yaml": "21bbd40526c7b515fecdc81d2f66e8bb0c75f129f9a381cbf5cb89991c27b3c8",
    "payloads/resource_exhaustion_requests_multipart.yaml": "9d14837bb8fa10f750e16a2ace2ad86f7b9f99c8247a4239d0f8d07c0adc9f60",
    "payloads/resource_exhaustion_riemann_theta.yaml": "2e8436d52d266cb608889ee8ec0cfb555f4e7b61ec4b6cfcbb7dcc9d3d557a33",
    "payloads/supply_chain.yaml": "4583e44d5b5842434eeafce9b7d243a32aba4e27763778f41c779435a703e202",
    "payloads/supply_chain_hnf.yaml": "359ebdb5d196a0668b3b22c659d18531dd447ab6cce2fd0b9f97a1a401b8f794",
    "payloads/supply_chain_requests_json_typing.yaml": "ef60cabfe258c11b04543958e28e816e862f8648a9a15446e39fc4a0751e9927",
    "payloads/supply_chain_requests_l10n.yaml": "c283e34c1c90c0a3f04fb1d362fd2193cc12c5de83096f6d638897c1c00180db",
    "payloads/supply_chain_requests_multipart.yaml": "5e41405d6bd1f9f25015997e72104c9906f371f2ddeccbd4b31dd4e8859e128a",
    "payloads/supply_chain_riemann_theta.yaml": "0a785d24e270a7f45052ab0d1cb967372cb1e01dce6a1bdd1ff7bab32358e928",
    "scripts/hnf/create_github_issue_issues.py": "178d656736293ba56c3252967330338607a978a31132c0513909696c9a798c9d",
    "scripts/requests_json_typing/create_github_issue_issues.py": "a4825aa598801ad241249756daf48db34c467728e72b4ac927f18be43445de7e",
    "scripts/requests_l10n/create_github_issue_issues.py": "dcc1385b6c4c92fb11081a501f15c21a58de29bf83ee5297c79d07a0b66e8eca",
    "scripts/requests_multipart/create_github_issue_issues.py": "343a0cd0b549af18cbb6b076b476d38dd763ef50399b84ea2273ea7d149ed32a",
    "scripts/riemann_theta/create_github_issue_issues.py": "9399e86472dbd42ae56521008d2b0bd411d84b35c02d500ded2b5c1c83389dfc",
    "scripts/run_benchmark.py": "b370d8f27712bbb217c68562c444f264c41b2b229619775862b358a9871eee8e",
    "scripts/sympy_matrix_det/create_github_issue_issues.py": "7c3d5dcfd19eab8e670926e28af20da6973812b9433a9258b0c699febf2a59c7",
}


@dataclass(frozen=True)
class Case:
    sample: str
    seed: str
    attack: str
    perturbation: str
    body: str
    title: str


def verify_data(data: Path) -> None:
    for name, expected in DATA_HASHES.items():
        actual = hashlib.sha256((data / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Released artifact file changed: {name}")


def read_constants(script: Path) -> dict:
    """Read only literal constants and the release's SEED_TAG payload names."""
    wanted = {
        "TOP",
        "MID",
        "BOT",
        "LEGIT_BODY_TOP",
        "LEGIT_BODY_MID",
        "LEGIT_BODY_BOT",
        "ISSUE_TITLE",
        "PERTS",
        "PERTURBATIONS",
        "SEED_TAG",
        "ATTACKS",
    }
    constants = {}
    for node in ast.parse(script.read_text(encoding="utf-8")).body:
        if (
            not isinstance(node, ast.Assign)
            or len(node.targets) != 1
            or not isinstance(node.targets[0], ast.Name)
        ):
            continue
        name = node.targets[0].id
        if name not in wanted:
            continue
        if name == "ATTACKS":
            attacks = []
            for pair in node.value.elts:
                key, code = pair.elts
                if isinstance(key, ast.JoinedStr):
                    parts = []
                    for part in key.values:
                        if (
                            isinstance(part, ast.FormattedValue)
                            and isinstance(part.value, ast.Name)
                            and part.value.id == "SEED_TAG"
                            and part.conversion == -1
                            and part.format_spec is None
                        ):
                            parts.append(constants["SEED_TAG"])
                        else:
                            parts.append(ast.literal_eval(part))
                    key = ast.Constant("".join(parts))
                attacks.append((ast.literal_eval(key), ast.literal_eval(code)))
            constants[name] = attacks
        else:
            constants[name] = ast.literal_eval(node.value)
    return constants


def all_cases(data: Path) -> list[Case]:
    cases = []
    for seed_name, seed in SEEDS.items():
        constants = read_constants(
            data / f"scripts/{seed_name}/create_github_issue_issues.py"
        )
        top, mid, bot = [
            constants[part if seed_name == "sympy_matrix_det" else f"LEGIT_BODY_{part}"]
            for part in ("TOP", "MID", "BOT")
        ]
        for payload_name, _ in constants["ATTACKS"]:
            attack = (
                payload_name.removesuffix(seed.payload_suffix)
                if seed.payload_suffix
                else payload_name
            )
            payloads = yaml.safe_load(
                (data / f"payloads/{attack}{seed.payload_suffix}.yaml").read_text(encoding="utf-8")
            )
            for position, language, caps, embedding, perturbation in constants.get(
                "PERTS", constants.get("PERTURBATIONS")
            ):
                payload = payloads[language]
                if caps == "allcaps":
                    payload = payload.upper()
                insertion = (
                    f"<!-- {payload} -->" if embedding == "html_comment" else payload
                )
                if position == "top":
                    body = insertion + "\n\n" + top + mid + bot
                elif position == "middle":
                    body = top + mid + "\n" + insertion + "\n\n" + bot
                elif position == "bottom":
                    body = top + mid + bot + "\n\n" + insertion
                else:
                    raise ValueError(f"Unknown released position: {position}")
                sample = f"{seed_name}:{attack}:{perturbation}"
                cases.append(
                    Case(
                        sample,
                        seed_name,
                        attack,
                        perturbation,
                        body,
                        constants["ISSUE_TITLE"],
                    )
                )
    return cases


def select_cases(cases: list[Case], *, seeds=None, samples=None) -> list[Case]:
    for label, requested, known in (
        ("seed", seeds, SEEDS),
        ("sample", samples, {case.sample for case in cases}),
    ):
        if requested is not None:
            if len(requested) != len(set(requested)):
                raise ValueError(f"Duplicate {label} filters")
            unknown = set(requested) - set(known)
            if unknown:
                raise ValueError(
                    f"Unknown {label} filters: {', '.join(sorted(unknown))}"
                )
    selected = [
        case
        for case in cases
        if (seeds is None or case.seed in seeds)
        and (samples is None or case.sample in samples)
    ]
    if not selected:
        raise ValueError("Filters select no cases")
    return selected
