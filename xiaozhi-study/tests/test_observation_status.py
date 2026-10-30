from app.analysis.observation_status import classify

def test_pending_is_not_classified_as_distraction_or_learning():
    assert classify({'candidate_state':'distracted_phone','window':{'confirmed':False}})=='confirming'

def test_hidden_landmarks_explain_uncertainty():
    assert classify({'version':2,'face_visible':False,'pose_visible':False})=='limited_view'

def test_legacy_invalid_and_missing_evidence_stay_unknown():
    for sample in (None,'bad','[]',{}, {'version':2,'face_visible':True}):
        assert classify(sample)=='insufficient_evidence'


def test_malformed_window_does_not_crash_summary():
    for window in ('bad',[1],True):
        assert classify({'candidate_state':'distracted_phone','window':window})=='insufficient_evidence'
