import pytest
from pydantic import ValidationError

from app.schemas.experiment import ExperimentCreate, ObservationCreate
from app.schemas.identity import ConsentAcceptIn, ProfileUpdateIn


def test_profile_text_is_trimmed_and_required_fields_reject_whitespace():
    payload = ProfileUpdateIn(
        nickname="  合成用户  ",
        goal="  改善记录习惯  ",
        constraints="   ",
    )

    assert payload.nickname == "合成用户"
    assert payload.goal == "改善记录习惯"
    assert payload.constraints == ""
    with pytest.raises(ValidationError):
        ProfileUpdateIn(nickname="   ")


def test_identifier_and_consent_version_are_normalized_before_validation():
    assert ExperimentCreate(action_id="  action-postmeal-walk  ").action_id == (
        "action-postmeal-walk"
    )
    assert ConsentAcceptIn(version="  2026-09-11.v1  ").version == "2026-09-11.v1"
    with pytest.raises(ValidationError):
        ExperimentCreate(action_id="   ")
    with pytest.raises(ValidationError):
        ExperimentCreate(action_id="a" * 37)
    with pytest.raises(ValidationError):
        ConsentAcceptIn(version="   ")


def test_observation_optional_text_is_trimmed_and_blank_values_become_null():
    payload = ObservationCreate(
        observed_on="2026-09-14",
        notes="  合成记录  ",
        unplanned_event="   ",
    )

    assert payload.notes == "合成记录"
    assert payload.unplanned_event is None
