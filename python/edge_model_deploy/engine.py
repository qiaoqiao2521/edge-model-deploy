import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class WordTimingSegment:
    word: str
    start_ms: int
    end_ms: int


class EdgeAudioPipeline:
    """端侧音频处理管线：转写、字级时间戳切分与语气词过滤"""

    FILLER_REGEX = re.compile(r"^(呃|啊|嗯|那个|这个|然后|就是说)+|(呃|啊|嗯|那个|这个|然后|就是说)+$|\b(um|uh|er|ah)\b", re.IGNORECASE)

    def filter_disfluencies(self, text: str) -> Tuple[str, List[str]]:
        """过滤口播常见冗余语气词 (对标商业剪辑 App 的 Disfluency Filter)"""
        dropped = []
        cleaned = text.strip()
        matches = self.FILLER_REGEX.findall(cleaned)
        for m in matches:
            val = next((item for item in m if item), None)
            if val:
                dropped.append(val)
        cleaned = self.FILLER_REGEX.sub("", cleaned).strip()
        return cleaned, dropped

    def process_transcript(self, raw_text: str, total_duration_sec: float = 3.0) -> Tuple[str, List[WordTimingSegment], List[str]]:
        cleaned_text, dropped_fillers = self.filter_disfluencies(raw_text)
        words = [w for w in re.split(r"(\s+|[，。！？,.!?])", cleaned_text) if w and not w.isspace()]
        if not words:
            return "", [], dropped_fillers

        total_ms = int(total_duration_sec * 1000)
        step_ms = total_ms // max(1, len(words))
        segments = []

        for idx, w in enumerate(words):
            start = idx * step_ms
            end = min(total_ms, (idx + 1) * step_ms)
            segments.append(WordTimingSegment(word=w, start_ms=start, end_ms=end))

        return cleaned_text, segments, dropped_fillers
