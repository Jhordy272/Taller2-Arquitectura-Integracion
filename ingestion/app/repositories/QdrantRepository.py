"""Stores fragments in Qdrant, and manages collections and the active alias."""
import uuid

from qdrant_client import QdrantClient, models

from app.models.Fragment import Fragment

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "lexical"

_ID_NAMESPACE = uuid.UUID("6f1d2c4e-8b7a-4f3e-9a21-5c0d7e6b1a90")
_INDEXED_FIELDS = ("validity_status", "code", "fragment_id", "injection_risk")


class QdrantRepository:
    def __init__(self, url: str) -> None:
        self._client = QdrantClient(url=url)

    def ensure_collection(self, name: str, dimensions: int, metadata: dict) -> None:
        """Create the collection once; its name carries the versions of its contents."""
        if self._client.collection_exists(name):
            return
        self._client.create_collection(
            collection_name=name,
            vectors_config={DENSE_VECTOR: models.VectorParams(size=dimensions, distance=models.Distance.COSINE)},
            sparse_vectors_config={SPARSE_VECTOR: models.SparseVectorParams(modifier=models.Modifier.IDF)},
            metadata=metadata,
        )
        for field in _INDEXED_FIELDS:
            schema = models.PayloadSchemaType.BOOL if field == "injection_risk" else models.PayloadSchemaType.KEYWORD
            self._client.create_payload_index(name, field_name=field, field_schema=schema)

    def replace_points(
        self,
        name: str,
        fragments: list[Fragment],
        dense_vectors: list[list[float]],
        sparse_vectors: list[tuple[list[int], list[float]]],
    ) -> None:
        """Upsert with deterministic ids, then drop points no longer in the corpus."""
        points = [
            models.PointStruct(
                id=self._point_id(fragment.fragment_id),
                vector={
                    DENSE_VECTOR: dense,
                    SPARSE_VECTOR: models.SparseVector(indices=sparse[0], values=sparse[1]),
                },
                payload=fragment.payload(),
            )
            for fragment, dense, sparse in zip(fragments, dense_vectors, sparse_vectors, strict=True)
        ]
        self._client.upsert(name, points=points, wait=True)

        current_ids = {point.id for point in points}
        stale_ids = [record.id for record in self._all_records(name) if record.id not in current_ids]
        if stale_ids:
            self._client.delete(name, points_selector=models.PointIdsList(points=stale_ids), wait=True)

    def sync_validity(self, name: str, entries: list[dict], default_status: str) -> tuple[int, list[str]]:
        """Copy the registry state to the fragments without touching vectors. A document
        missing from the registry falls back to the default status, so it fails closed."""
        registered = {(entry["code"], entry["version"]) for entry in entries}
        for entry in entries:
            self._set_document_state(
                name,
                entry["code"],
                entry["version"],
                {
                    "validity_status": entry["status"],
                    "certification_state": entry["certification_state"],
                    "superseded_by": entry["superseded_by"],
                },
            )

        unregistered = {
            (record.payload["code"], record.payload["version"])
            for record in self._all_records(name, with_payload=["code", "version"])
        } - registered
        for code, version in unregistered:
            self._set_document_state(
                name, code, version, {"validity_status": default_status, "certification_state": "pending", "superseded_by": None}
            )
        return len(entries), sorted(f"{code}@{version}" for code, version in unregistered)

    def _set_document_state(self, name: str, code: str, version: str, state: dict) -> None:
        self._client.set_payload(
            name,
            payload=state,
            points=models.Filter(
                must=[
                    models.FieldCondition(key="code", match=models.MatchValue(value=code)),
                    models.FieldCondition(key="version", match=models.MatchValue(value=version)),
                ]
            ),
            wait=True,
        )

    def active_collection(self, alias: str) -> str | None:
        for entry in self._client.get_aliases().aliases:
            if entry.alias_name == alias:
                return entry.collection_name
        return None

    def activate(self, alias: str, name: str) -> None:
        """Point the alias at the collection in a single atomic operation."""
        operations: list = [
            models.CreateAliasOperation(create_alias=models.CreateAlias(collection_name=name, alias_name=alias))
        ]
        if self.active_collection(alias) is not None:
            operations.insert(0, models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=alias)))
        self._client.update_collection_aliases(change_aliases_operations=operations)

    def _all_records(self, name: str, with_payload: bool | list[str] = False) -> list:
        records, offset = [], None
        while True:
            page, offset = self._client.scroll(name, limit=256, offset=offset, with_payload=with_payload)
            records.extend(page)
            if offset is None:
                return records

    def _point_id(self, fragment_id: str) -> str:
        return str(uuid.uuid5(_ID_NAMESPACE, fragment_id))
