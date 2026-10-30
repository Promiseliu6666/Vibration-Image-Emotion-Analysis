"""Admin monthly reports for the shared workspace. Timers remain account-scoped."""
import calendar
import io
import re
from datetime import datetime,timedelta
from xml.sax.saxutils import escape
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import Response
from app.api.api_router import require_admin
from app.core.db import get_connection
router=APIRouter(prefix='/api/study/reports')
LABELS={'engaged_reading':'投入阅读','engaged_writing':'投入书写','engaged_screen':'听讲 / 朝向学习区','engaged_computer':'电脑操作','engaged_hand_raising':'举手互动','engaged_discussing':'讨论交流','distracted_phone':'使用手机','distracted_away':'视线离开','thinking':'活动未确认','resting':'休息','standing':'站立活动','fatigued':'疲劳','distracted':'分心'}
def period(month):
    if not re.fullmatch(r'\d{4}-\d{2}',month):raise HTTPException(422,'请选择有效月份')
    try:
        y,m=map(int,month.split('-'));a=datetime(y,m,1)
    except ValueError:raise HTTPException(422,'请选择有效月份')
    now=datetime.utcnow()+timedelta(hours=8)
    if y<2000 or a>datetime(now.year,now.month,1):raise HTTPException(422,'只能查看当前或过去月份')
    b=datetime(y+1,1,1) if m==12 else datetime(y,m+1,1)
    return a-timedelta(hours=8),b-timedelta(hours=8)
def summarize(month,device,rows,timer_minutes,hours=None):
    counts={};days=set();weeks={}
    for r in rows:
        state=r['learning_state'] or 'thinking';n=int(r['n']);counts[state]=counts.get(state,0)+n;day=str(r['day']);days.add(day)
        w=weeks.setdefault((int(day[-2:])-1)//7+1,{'samples':0,'engaged':0});w['samples']+=n;w['engaged']+=n if state.startswith('engaged_') else 0
    total=sum(counts.values());pct=lambda n:round(n/total*100,1) if total else None
    engaged=sum(v for k,v in counts.items() if k.startswith('engaged_'));unknown=counts.get('thinking',0);phone=counts.get('distracted_phone',0)
    from app.analysis.health_dimensions import summarize as summarize_dimensions
    dimensions=summarize_dimensions(counts,total)
    vision=next((d for d in dimensions if d['key']=='vision'),None)
    notes=[];plans=[]
    if total:
        notes.append(f'在 {len(days)} 天记录到 {total} 个有效观察样本，投入状态样本占比 {pct(engaged)}%。此比例不是时长，也不是成绩。')
        if total<100 or len(days)<3:notes.append('记录覆盖较少，仅能描述已观察到的片段，不能代表整个月。')
        if unknown:notes.append(f'{pct(unknown)}% 的样本处于“活动未确认”，尚未确认具体行为。')
        if phone:notes.append(f'手机使用占有效样本 {pct(phone)}%，无法据此确定使用分钟数或用途。')
        if phone/total>=.1:plans.append({'title':'尝试减少手机干扰','detail':'非必要时把手机放在视线外，每段学习结束集中查看；留意是否能更少地中断正在做的任务。'})
        if counts.get('distracted_away',0)/total>=.15:plans.append({'title':'尝试更清楚的学习段','detail':'试用 25 分钟计时和短暂休息；视线离开也可能是正常思考，回看具体片段后再决定是否调整。'})
        if vision and vision['pct'] and vision['pct']>=60:
            notes.append(f'用眼负荷相关样本占 {vision["pct"]}%，连续近距离与屏幕用眼偏多（同一状态可同时计入多个维度，占比之和不等于 100%）。')
            plans.append({'title':'安排用眼休息','detail':'每连续用眼约 45 分钟起身远眺片刻，让画面外的休息也留出时间；下个月比较用眼负荷占比与休息样本的变化。'})
    else:notes.append('本月暂无识别到人的有效观察样本，无法分析这段时间的状态。')
    plans.append({'title':'每周回看一次','detail':'每周固定一天回顾学习与休息的安排，记录哪些习惯让自己更容易投入，再选择一项小改变尝试。' if total else '先选一个容易坚持的学习时段，明确一项要完成的任务，并在结束后回顾自己的投入与休息情况。'})
    plans.append({'title':'建立可持续的计时目标','detail':'以自己实际完成的节奏制定目标，再小幅调整，不根据样本比例推算时长。' if timer_minutes else '先为每天安排一段容易完成的学习时间，结束后回顾实际完成情况，再逐步调整目标。'})
    hour_counts=[0]*24
    for r in (hours or []):
        h=int(r['h'])
        if 0<=h<24:hour_counts[h]=int(r['n'])
    return {'month':month,'device':device,'generated_at':(datetime.utcnow()+timedelta(hours=8)).strftime('%Y-%m-%d %H:%M'),'partial_month':month==(datetime.utcnow()+timedelta(hours=8)).strftime('%Y-%m'),'samples':total,'observed_days':len(days),'engaged_pct':pct(engaged),'phone_pct':pct(phone),'unknown_pct':pct(unknown),'timer_minutes':round(timer_minutes),'dimensions':dimensions,'hours':hour_counts,'distribution':[{'label':LABELS.get(k,'其他已记录行为'),'samples':v,'pct':pct(v)} for k,v in sorted(counts.items(),key=lambda x:-x[1])],'weeks':[{'week':k,'samples':v['samples'],'engaged_pct':round(v['engaged']/v['samples']*100,1)} for k,v in sorted(weeks.items())],'notes':notes,'plans':plans,'scope':'北京时间；设备统计属于本共享工作空间，计时仅属于当前账户。仅包含识别到人的有效样本，不将样本数换算为时长；未结束的计时不计入。健康维度为标签式归属，同一状态可同时计入多个维度，占比之和大于 100% 属正常。没有记录不等于没有学习。'}
def collect(month,device_id,username):
    # Both routes require an enabled admin via require_admin; shared devices have no private owners.
    start,end=period(month);c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT device_id,name FROM devices WHERE device_id=%s',(device_id,));device=q.fetchone()
            if not device:raise HTTPException(404,'设备不存在，请重新选择')
            q.execute("SELECT DATE(a.timestamp+INTERVAL 8 HOUR) AS day,a.learning_state,COUNT(*) AS n FROM analysis_results a JOIN sessions s ON s.id=a.session_id WHERE s.device_id=%s AND a.timestamp>=%s AND a.timestamp<%s AND a.person_present=1 AND a.learning_state<>'absent' GROUP BY day,a.learning_state",(device_id,start,end));rows=q.fetchall()
            q.execute('SELECT COALESCE(SUM(GREATEST(0,TIMESTAMPDIFF(SECOND,GREATEST(started_at,%s),LEAST(ended_at,DATE_ADD(started_at,INTERVAL minutes MINUTE),%s)))),0) AS seconds FROM study_timers WHERE username=%s AND ended_at IS NOT NULL AND started_at<%s AND ended_at>%s',(start,end,username,end,start));minutes=float(q.fetchone()['seconds'])/60
            q.execute("SELECT HOUR(a.timestamp+INTERVAL 8 HOUR) AS h,COUNT(*) AS n FROM analysis_results a JOIN sessions s ON s.id=a.session_id WHERE s.device_id=%s AND a.timestamp>=%s AND a.timestamp<%s AND a.person_present=1 AND a.learning_state<>'absent' GROUP BY h",(device_id,start,end));hours=q.fetchall()
            q.execute("SELECT COUNT(*) n FROM health_actions WHERE username=%s AND device_id=%s AND kind='break' AND response='done' AND created_at>=%s AND created_at<%s",(username,device_id,start,end));breaks=int(q.fetchone()['n'])
        report=summarize(month,device,rows,minutes,hours)
        report['notes'].append(f'本月本人反馈已休息活动 {breaks} 次；这是自报记录，不是摄像头验证的休息时长或健康改善。')
        return report
    finally:c.close()
@router.get('/monthly')
def monthly(month:str,device_id:str,username=Depends(require_admin)):return collect(month,device_id,username)
def vision_text(report):
    vision=next((d for d in (report.get('dimensions') or []) if d['key']=='vision'),None)
    return (str(vision['pct'])+'%') if vision and vision.get('pct') is not None else '—'
def make_pdf(r):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
    from pathlib import Path
    font='StudyChinese'
    if font not in pdfmetrics.getRegisteredFontNames():
        if Path('C:/Windows/Fonts/simsun.ttc').exists():pdfmetrics.registerFont(TTFont(font,'C:/Windows/Fonts/simsun.ttc',subfontIndex=0))
        else:font='STSong-Light';pdfmetrics.registerFont(UnicodeCIDFont(font))
    b=io.BytesIO();doc=SimpleDocTemplate(b,pagesize=(595,842),leftMargin=46,rightMargin=46,topMargin=48,bottomMargin=48,title='月度健康报告',author='小智伴学')
    body=ParagraphStyle('body',fontName=font,fontSize=11,leading=19,spaceAfter=10,textColor=colors.HexColor('#364b3b'),wordWrap='CJK');title=ParagraphStyle('title',parent=body,fontSize=23,leading=32,spaceAfter=18);head=ParagraphStyle('head',parent=body,fontSize=15,leading=23,spaceBefore=12)
    P=lambda t,style=body:Paragraph(escape(str(t)),style)
    story=[P('月度健康报告',title),P(r['month']+' · '+(r['device']['name'] or r['device']['device_id']),head),P('当前月阶段报告' if r['partial_month'] else '月度回顾')]
    t=Table([[P('有效样本'),P('有记录天数'),P('用眼负荷占比')],[P(r['samples']),P(str(r['observed_days'])+' 天'),P(vision_text(r))]],colWidths=[167]*3);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#edf2e3')),('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12)]));story += [t,Spacer(1,16),P('本月观察',head)]+[P(n) for n in r['notes']]+[P('行为分布',head)]
    story += [P(f"{d['label']}：{d['samples']} 个样本 / {d['pct']}%") for d in r['distribution']]
    story += [PageBreak(),P('每周变化与下月安排',title)]
    story += [P(f"第 {w['week']} 段（每 7 天一段）：{w['samples']} 个样本，学习活动占比 {w['engaged_pct']}%。") for w in r['weeks']]
    for i,p in enumerate(r['plans'],1):story += [P(str(i)+'. '+p['title'],head),P(p['detail'])]
    story += [P('数据口径',head),P(r['scope']),P('生成时间：'+r['generated_at'])]
    def footer(c,d):
        c.setFont(font,9);c.setFillColor(colors.HexColor('#69725e'));c.drawString(46,25,'小智伴学 · '+r['month']);c.drawRightString(549,25,str(d.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer);return b.getvalue()
@router.get('/monthly.pdf')
def monthly_pdf(month:str,device_id:str,username=Depends(require_admin)):
    return Response(make_pdf(collect(month,device_id,username)),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="study-report-{month}.pdf"','Cache-Control':'no-store'})
