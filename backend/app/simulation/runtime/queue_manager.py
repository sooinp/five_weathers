"""
backend/app/simulation/runtime/queue_manager.py

UGV 대기열 관리.
우선순위 점수 기반 정렬 대기열.
"""

import heapq
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(order=True)
class QueueItem:
    priority: float        # 낮을수록 높은 우선순위 (heapq는 min-heap)
    unit_no: int = field(compare=False)
    asset_code: str = field(compare=False)
    wait_time_sec: int = field(compare=False, default=0)


class QueueManager:
    def __init__(self) -> None:
        self._heap: list[QueueItem] = []
        self._in_queue: set[int] = set()

    def enqueue(self, unit_no: int, asset_code: str, priority_score: float) -> None:
        """높은 priority_score → 낮은 heap priority (우선 처리)."""
        if unit_no in self._in_queue:
            return
        item = QueueItem(
            priority=-priority_score,  # 음수 변환 (max-priority 효과)
            unit_no=unit_no,
            asset_code=asset_code,
        )
        heapq.heappush(self._heap, item)
        self._in_queue.add(unit_no)
        logger.debug("enqueued unit_no=%d score=%.3f", unit_no, priority_score)

    def dequeue(self) -> QueueItem | None:
        if not self._heap:
            return None
        item = heapq.heappop(self._heap)
        self._in_queue.discard(item.unit_no)
        return item

    def peek(self) -> QueueItem | None:
        return self._heap[0] if self._heap else None

    @property
    def length(self) -> int:
        return len(self._heap)

    def items(self) -> list[QueueItem]:
        return sorted(self._heap)
