from dataclasses import dataclass

CURATED_QUERY_PREFIX = "curated://"


@dataclass(frozen=True)
class CuratedAsset:
    asset_id: str
    asset_type: str
    title: str
    prompt_hint: str


CURATED_ASSET_LIBRARY = {
    ("biology", "photosynthesis", "explain_core"): CuratedAsset(
        asset_id="biology/photosynthesis/core-diagram",
        asset_type="diagram",
        title="Photosynthesis process diagram",
        prompt_hint="Use a labeled chloroplast and input/output arrows.",
    ),
}


def encode_curated_image_query(asset: CuratedAsset) -> str:
    return f"{CURATED_QUERY_PREFIX}{asset.asset_id}|{asset.prompt_hint}"


def is_curated_image_query(query: str | None) -> bool:
    return bool(query and query.startswith(CURATED_QUERY_PREFIX))


def lookup_curated_asset(*, subject: str, topic: str, pedagogical_role: str) -> CuratedAsset | None:
    key = (subject.strip().lower(), topic.strip().lower(), pedagogical_role.strip().lower())
    return CURATED_ASSET_LIBRARY.get(key)


def lookup_curated_asset_by_id(asset_id: str) -> CuratedAsset | None:
    normalized_asset_id = asset_id.strip()
    for asset in CURATED_ASSET_LIBRARY.values():
        if asset.asset_id == normalized_asset_id:
            return asset
    return None


def parse_curated_image_query(query: str | None) -> tuple[CuratedAsset | None, str | None]:
    if not is_curated_image_query(query):
        return None, None

    payload = query[len(CURATED_QUERY_PREFIX) :]
    asset_id, separator, prompt_hint = payload.partition("|")
    if not asset_id:
        return None, None

    asset = lookup_curated_asset_by_id(asset_id)
    if asset is None:
        return None, prompt_hint if separator else None

    resolved_hint = prompt_hint.strip() if separator and prompt_hint.strip() else asset.prompt_hint
    return asset, resolved_hint
