"""B2C 테스트 체크포인트 관리"""
import json
from datetime import datetime
from pathlib import Path

CHECKPOINT_PATH = Path("qa_artifacts/b2c_checkpoint.json")


class B2CCheckpoint:
    PHASES = [
        "1", "1.2", "1.5",
        "2", "3", "4", "4.5", "4.6",
        "5", "5.5", "6", "7", "7.5", "7.6", "8",
    ]

    def __init__(self):
        self.data = {
            "created_at": "",
            "updated_at": "",
            "environment": "",
            "shop_name": "",
            "completed_phases": [],
            "failed_phase": None,
            "state": {},
        }

    def save(self):
        self.data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_PATH.write_text(json.dumps(self.data, ensure_ascii=False, indent=2))

    @classmethod
    def load(cls):
        cp = cls()
        if CHECKPOINT_PATH.exists():
            cp.data = json.loads(CHECKPOINT_PATH.read_text())
        return cp

    @classmethod
    def exists(cls):
        return CHECKPOINT_PATH.exists()

    @classmethod
    def clear(cls):
        if CHECKPOINT_PATH.exists():
            CHECKPOINT_PATH.unlink()

    def mark_start(self, shop_name: str, environment: str):
        self.data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data["shop_name"] = shop_name
        self.data["environment"] = environment
        self.data["completed_phases"] = []
        self.data["failed_phase"] = None
        self.save()

    def mark_phase_done(self, phase: str, extra_state: dict = None):
        if phase not in self.data["completed_phases"]:
            self.data["completed_phases"].append(phase)
        self.data["failed_phase"] = None
        if extra_state:
            self.data["state"].update(extra_state)
        self.save()

    def mark_phase_failed(self, phase: str, error: str = ""):
        self.data["failed_phase"] = phase
        self.data["state"]["last_error"] = error
        self.save()

    def is_phase_done(self, phase: str) -> bool:
        return phase in self.data.get("completed_phases", [])

    def get_resume_phase(self) -> str | None:
        """다음에 실행할 Phase 반환. 전부 완료면 None."""
        for phase in self.PHASES:
            if phase not in self.data.get("completed_phases", []):
                return phase
        return None

    @property
    def shop_name(self):
        return self.data.get("shop_name", "")

    @property
    def environment(self):
        return self.data.get("environment", "")

    @property
    def state(self):
        return self.data.get("state", {})

    def summary(self) -> str:
        completed = self.data.get("completed_phases", [])
        failed = self.data.get("failed_phase")
        resume = self.get_resume_phase()
        lines = [
            f"  샵: {self.shop_name}",
            f"  환경: {self.environment}",
            f"  완료: {' → '.join(completed) if completed else '없음'}",
        ]
        if failed:
            lines.append(f"  실패: Phase {failed}")
        if resume:
            lines.append(f"  다음: Phase {resume}부터 이어서 진행")
        else:
            lines.append("  상태: 전체 완료")
        return "\n".join(lines)
