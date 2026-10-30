"""Explain uncertain samples without turning them into positive or negative behavior."""
import json

def classify(evidence):
    try:
        data=json.loads(evidence or '{}') if isinstance(evidence,str) else evidence or {}
        if not isinstance(data,dict):return 'insufficient_evidence'
    except (TypeError,ValueError):return 'insufficient_evidence'
    window=data.get('window') or {}
    if not isinstance(window,dict):return 'insufficient_evidence'
    if data.get('candidate_state') not in (None,'thinking','absent') and not window.get('confirmed'):
        return 'confirming'
    if data.get('version')==2 and data.get('face_visible') is False and data.get('pose_visible') is False:
        return 'limited_view'
    return 'insufficient_evidence'

LABELS={'confirming':'等待连续确认','limited_view':'面部或身体遮挡','insufficient_evidence':'具体活动证据不足'}
