# %%
from pydantic import BaseModel, field_validator


# %%
class JobOpportunity(BaseModel):
    title: str
    company: str | None = None
    location: str | None = None
    is_junior: bool
    tech_stack: list[str]
    contact_info: str | None = None
    job_link: str
    raw_text: str
    message_date: str | None = None  # ISO 8601 UTC — Telegram message post time
    source_group: str | None = None  # Telegram group this job was fetched from


# %%
class ScoredJob(JobOpportunity):
    confidence_score: int
    fit_reasoning: str

    @field_validator("confidence_score")
    @classmethod
    def score_in_range(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError(f"confidence_score must be 1-10, got {v}")
        return v


# %%
if __name__ == "__main__":
    job = ScoredJob(
        title="Data Analyst",
        company="Acme Corp",
        location="Tel Aviv",
        is_junior=True,
        tech_stack=["Python", "SQL", "Tableau"],
        contact_info="@recruiter",
        job_link="https://example.com/apply",
        raw_text="We are looking for a junior data analyst...",
        confidence_score=8,
        fit_reasoning="Strong SQL and Python match; junior-friendly role.",
    )
    print(job.model_dump_json(indent=2))
# %%
