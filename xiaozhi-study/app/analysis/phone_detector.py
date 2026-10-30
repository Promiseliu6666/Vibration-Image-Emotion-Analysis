"""Local COCO SSD object evidence. Never infer phone use from posture alone."""
from pathlib import Path
import threading
import numpy as np
import cv2

from app.core.paths import MODELS_DIR

MODEL_PATH=MODELS_DIR/'phone_ssd.onnx'
_session=None
_lock=threading.Lock()

def detect(frame, phone_threshold=.55):
    global _session
    if not MODEL_PATH.exists(): return {'available':False,'boxes':[]}
    with _lock:
        if _session is None:
            import onnxruntime as ort
            options=ort.SessionOptions();options.intra_op_num_threads=2
            options.inter_op_num_threads=1
            options.add_session_config_entry('session.intra_op.allow_spinning','0')
            options.add_session_config_entry('session.inter_op.allow_spinning','0')
            _session=ort.InferenceSession(str(MODEL_PATH),sess_options=options,providers=['CPUExecutionProvider'])
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        # Preserve aspect ratio and original details, bounded for CPU work.
        if max(rgb.shape[:2])>640:
            scale=640/max(rgb.shape[:2]);rgb=cv2.resize(rgb,(round(rgb.shape[1]*scale),round(rgb.shape[0]*scale)))
        outputs=['num_detections','detection_boxes','detection_scores','detection_classes']
        count,boxes,scores,classes=_session.run(outputs,{_session.get_inputs()[0].name:rgb[None].astype(np.uint8)})
    people=[]
    phones=[]
    objects=[]
    for box,score,cls in zip(boxes[0][:int(count[0])],scores[0],classes[0]):
        if int(cls)==1 and score>=.5:
            y1,x1,y2,x2=map(float,box)
            if 0<=x1<x2<=1 and 0<=y1<y2<=1 and (x2-x1)*(y2-y1)>=.025:
                people.append({'box':[x1,y1,x2,y2],'confidence':round(float(score),3)})
        if int(cls) in (77,84,73,76) and score >= (phone_threshold if int(cls)==77 else .55):
            y1,x1,y2,x2=map(float,box)
            if 0<=x1<x2<=1 and 0<=y1<y2<=1:
                item={'box':[x1,y1,x2,y2],'confidence':round(float(score),3)}
                if int(cls)==77:phones.append(item)
                else:objects.append({**item,'kind':{84:'book',73:'laptop',76:'keyboard'}[int(cls)]})
    return {'available':True,'boxes':phones,'objects':objects,'people':people}

def held_by_person(detections, pose):
    if not pose or not pose.pose_landmarks: return False
    lm=pose.pose_landmarks.landmark
    if not matches_main_person(detections.get('people',[]),pose):
        return False
    for phone in detections.get('boxes',[]):
        x1,y1,x2,y2=phone['box'];margin=max(.035,min(.10,max(x2-x1,y2-y1)*.65))
        for index in (15,16,19,20):
            p=lm[index]
            if p.visibility>=.65 and x1-margin<=p.x<=x2+margin and y1-margin<=p.y<=y2+margin:
                return True
    return False


def refine_hands(frame, detections, pose):
    """Resolve small handheld objects with bounded crops, mapping boxes back exactly."""
    if not pose or not pose.pose_landmarks:
        return detections
    if not matches_main_person(detections.get('people',[]),pose):
        return {**detections,'hand_crops':0,'crop_skipped':'background_pose'}
    lm=pose.pose_landmarks.landmark
    height,width=frame.shape[:2]
    regions=[]
    for wrist in (15,16):
        point=lm[wrist]
        if point.visibility < .5 or not (0<=point.x<=1 and 0<=point.y<=1):
            continue
        # Include objects above the palm, not just the wrist itself.
        x1=max(0,int((point.x-.22)*width));x2=min(width,int((point.x+.22)*width))
        y1=max(0,int((point.y-.35)*height));y2=min(height,int((point.y+.15)*height))
        if x2-x1<32 or y2-y1<32:
            continue
        if any(abs((x1+x2)/2-(a+c)/2)<width*.12 and abs((y1+y2)/2-(b+d)/2)<height*.12 for a,b,c,d in regions):
            continue
        regions.append((x1,y1,x2,y2))
    result={**detections,'boxes':list(detections.get('boxes',[])),'hand_crops':len(regions)}
    for x1,y1,x2,y2 in regions:
        try:
            local=detect(frame[y1:y2,x1:x2], phone_threshold=.4)
        except Exception as exc:
            result['hand_crop_error']=type(exc).__name__
            continue
        for item in local.get('boxes',[]):
            a,b,c,d=item['box']
            box=[(x1+a*(x2-x1))/width,(y1+b*(y2-y1))/height,(x1+c*(x2-x1))/width,(y1+d*(y2-y1))/height]
            result['boxes'].append({**item,'box':box,'source':'hand_crop'})
    result['boxes']=merge_phone_boxes(result['boxes'])
    return result


def matches_main_person(people, pose):
    if not people:
        return True  # Partial poses can still provide evidence when object detection misses a person.
    if not pose or not pose.pose_landmarks:
        return False
    main=max(people,key=lambda p:(p['box'][2]-p['box'][0])*(p['box'][3]-p['box'][1]))
    x1,y1,x2,y2=main['box']
    points=[pose.pose_landmarks.landmark[i] for i in (0,11,12) if pose.pose_landmarks.landmark[i].visibility>=.65]
    return bool(points) and any(x1-.03<=v.x<=x2+.03 and y1-.03<=v.y<=y2+.03 for v in points)

def touches_learning_object(objects, pose, people=None):
    """Require visible fingertips in the object, not a wrist near a large keyboard."""
    if not pose or not pose.pose_landmarks or not matches_main_person(people or [],pose):
        return False
    for obj in objects:
        x1,y1,x2,y2=obj['box']
        for i in (19,20):
            finger=pose.pose_landmarks.landmark[i]
            if finger.visibility>=.65 and x1-.015<=finger.x<=x2+.015 and y1-.015<=finger.y<=y2+.015:
                return True
    return False


def merge_phone_boxes(boxes):
    """Filter malformed detections and collapse overlapping views of one object."""
    valid=[]
    for item in boxes:
        try:
            x1,y1,x2,y2=map(float,item['box']);score=float(item['confidence'])
            if not np.isfinite([x1,y1,x2,y2,score]).all() or not (0<=x1<x2<=1 and 0<=y1<y2<=1 and 0<=score<=1):continue
            valid.append({**item,'box':[x1,y1,x2,y2],'confidence':score})
        except (KeyError,ValueError,TypeError):continue
    kept=[]
    for item in sorted(valid,key=lambda b:b['confidence'],reverse=True):
        a,b,c,d=item['box'];area=(c-a)*(d-b);duplicate=False
        for other in kept:
            x,y,z,w=other['box'];intersection=max(0,min(c,z)-max(a,x))*max(0,min(d,w)-max(b,y))
            union=area+(z-x)*(w-y)-intersection
            if union>0 and intersection/union>.6:duplicate=True;break
        if not duplicate:kept.append(item)
    return kept
