"""Runs filtered searches against the active collection (ADR-01, ADR-05)."""
from qdrant_client import QdrantClient, models

from app.models.RetrievedFragment import RetrievedFragment, SearchOutcome

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "lexical"

# Fixed here on purpose: callers cannot search documents that are not valid.
_VALID_ONLY = models.Filter(
    must=[models.FieldCondition(key="validity_status", match=models.MatchValue(value="valid"))]
)


def stable_order(fragments: list[RetrievedFragment]) -> list[RetrievedFragment]:
    """Sort by score and break ties by id: the engine does not guarantee an order among
    equal scores, and the composed answer must be reproducible (ADR-03)."""
    return sorted(fragments, key=lambda fragment: (-fragment.score, fragment.fragment_id))


class QdrantSearchRepository:
    def __init__(self, url: str, alias: str) -> None:
        self._client = QdrantClient(url=url)
        self._alias = alias

    def collection_metadata(self) -> dict:
        """Return the versions recorded when the collection was built (ADR-04)."""
        return self._client.get_collection(self._alias).config.metadata or {}

    def search(
        self,
        dense_vector: list[float],
        sparse_vector: tuple[list[int], list[float]],
        candidates: int,
        limit: int,
    ) -> SearchOutcome:
        """Run hybrid, dense and lexical searches in one batch, each with the filter
        inside every branch, so that the filter applies during the search."""
        branches = [self._dense_branch(dense_vector, candidates)]
        if sparse_vector[0]:
            branches.append(self._lexical_branch(sparse_vector, candidates))

        requests = [
            models.QueryRequest(
                prefetch=branches,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                filter=_VALID_ONLY,
                # Every fused candidate: the cut to the limit must happen after the stable sort.
                limit=candidates * len(branches),
                with_payload=True,
            ),
            models.QueryRequest(
                query=dense_vector,
                using=DENSE_VECTOR,
                filter=_VALID_ONLY,
                limit=candidates,
                with_payload=True,
            ),
        ]
        if sparse_vector[0]:
            requests.append(
                models.QueryRequest(
                    query=models.SparseVector(indices=sparse_vector[0], values=sparse_vector[1]),
                    using=SPARSE_VECTOR,
                    filter=_VALID_ONLY,
                    limit=candidates,
                    with_payload=True,
                )
            )

        responses = self._client.query_batch_points(self._alias, requests=requests)
        hybrid = stable_order(self._to_fragments(responses[0]))[:limit]
        dense = stable_order(self._to_fragments(responses[1]))
        lexical = stable_order(self._to_fragments(responses[2])) if sparse_vector[0] else []
        return SearchOutcome(hybrid=hybrid, dense=dense, lexical=lexical)

    def get_fragment(self, fragment_id: str) -> RetrievedFragment | None:
        """Fetch one valid fragment by id; a fragment that is not valid is not returned."""
        condition = models.FieldCondition(key="fragment_id", match=models.MatchValue(value=fragment_id))
        points, _ = self._client.scroll(
            self._alias,
            scroll_filter=models.Filter(must=[condition, *_VALID_ONLY.must]),
            limit=1,
            with_payload=True,
        )
        return self._to_fragment(points[0], score=0.0) if points else None

    def _dense_branch(self, dense_vector: list[float], candidates: int) -> models.Prefetch:
        return models.Prefetch(query=dense_vector, using=DENSE_VECTOR, filter=_VALID_ONLY, limit=candidates)

    def _lexical_branch(self, sparse_vector: tuple[list[int], list[float]], candidates: int) -> models.Prefetch:
        return models.Prefetch(
            query=models.SparseVector(indices=sparse_vector[0], values=sparse_vector[1]),
            using=SPARSE_VECTOR,
            filter=_VALID_ONLY,
            limit=candidates,
        )

    def _to_fragments(self, response: models.QueryResponse) -> list[RetrievedFragment]:
        return [self._to_fragment(point, point.score) for point in response.points]

    def _to_fragment(self, point, score: float) -> RetrievedFragment:
        return RetrievedFragment(
            fragment_id=point.payload["fragment_id"],
            score=score,
            code=point.payload["code"],
            version=point.payload["version"],
            title=point.payload["title"],
            document_type=point.payload["document_type"],
            document_class=point.payload["document_class"],
            issue_date=point.payload["issue_date"],
            issuing_area=point.payload["issuing_area"],
            section_id=point.payload["section_id"],
            section_title=point.payload["section_title"],
            parent_section_id=point.payload["parent_section_id"],
            text=point.payload["text"],
            indexed_text=point.payload["indexed_text"],
            validity_status=point.payload["validity_status"],
            injection_risk=point.payload["injection_risk"],
        )
