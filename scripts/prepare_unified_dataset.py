from __future__ import annotations

import argparse,csv,json,re
from pathlib import Path
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]
BEAUTY_MAP={"stayingpower":"product_quality","texture":"product_quality","smell":"product_quality","colour":"product_quality","price":"price","shipping":"delivery","packing":"packaging"}
UIT_MAP={"SCREEN":"product_quality","CAMERA":"product_quality","FEATURES":"product_quality","BATTERY":"product_quality","PERFORMANCE":"product_quality","STORAGE":"product_quality","DESIGN":"product_quality","PRICE":"price"}
SERVICE_TERMS=re.compile(r"nhân viên|tư vấn|bảo hành|hậu mãi|hỗ trợ|đổi trả|đổi máy|chăm sóc|shop",re.I)

def merge(anns):
 grouped=defaultdict(set)
 for a,s in anns: grouped[a].add(s.lower())
 out=[]
 for aspect,vals in grouped.items():
  if 'mixed' in vals or ('positive'in vals and 'negative'in vals):sent='mixed'
  elif 'negative'in vals:sent='negative'
  elif 'positive'in vals:sent='positive'
  else:sent='neutral'
  out.append({"aspect":aspect,"sentiment":sent})
 return sorted(out,key=lambda x:x['aspect'])

def beauty(path,split):
 rows=[]
 with path.open(encoding='utf-8-sig',newline='') as f:
  for i,r in enumerate(csv.DictReader(f),1):
   anns=[]
   for src,dst in BEAUTY_MAP.items():
    val=(r.get(src)or'').strip().lower()
    if val in {'positive','neutral','negative'}:anns.append((dst,val))
   # `others` is spam in this source; do not map to project `other`.
   rows.append({"id":f"beauty_{split}_{i}","text":str(r.get('data')or'').strip(),"annotations":merge(anns),"split":split,"source":"beauty_absa_2022","source_other_is_spam":bool((r.get('others')or'').strip()),"requires_manual_review":False,"safe_for_auto_gold":True})
 return rows

def uit(path,split,allow_service=False):
 rows=[]; ambiguous=[]
 # GitHub JSONL contains one JSON object per physical/logical record. Python line parser is valid for downloaded raw file.
 with path.open(encoding='utf-8') as f:
  for i,line in enumerate(f,1):
   if not line.strip():continue
   r=json.loads(line);text=str(r.get('text')or'');anns=[];unmapped_meaningful=[]
   for label in r.get('labels')or[]:
    if len(label)<3:continue
    start,end,raw=int(label[0]),int(label[1]),str(label[2])
    if '#' not in raw:continue
    aspect,sent=raw.rsplit('#',1);sent=sent.lower()
    if aspect in UIT_MAP:
     anns.append((UIT_MAP[aspect],sent))
    elif aspect=='SER&ACC':
     span=text[start:end]
     unmapped_meaningful.append(raw)
     if allow_service and SERVICE_TERMS.search(span): anns.append(('customer_service',sent))
     ambiguous.append({"id":f"uit_{split}_{i}","span":span,"label":raw,"reason":"SER&ACC mixes service and accessories; whole row requires human verification before project gold"})
    elif aspect=='GENERAL':
     unmapped_meaningful.append(raw)
     ambiguous.append({"id":f"uit_{split}_{i}","span":text[start:end],"label":raw,"reason":"GENERAL is broader than the project taxonomy; whole row is excluded from automatic gold"})
    else:
     unmapped_meaningful.append(raw)
     ambiguous.append({"id":f"uit_{split}_{i}","span":text[start:end],"label":raw,"reason":"Unrecognized upstream aspect; human mapping required"})
   rows.append({
    "id":f"uit_{split}_{i}","text":text.strip(),"annotations":merge(anns),"split":split,"source":"UIT-ViSD4SA",
    "requires_manual_review":bool(unmapped_meaningful),
    "safe_for_auto_gold":not bool(unmapped_meaningful),
    "unmapped_upstream_labels":unmapped_meaningful,
   })
 return rows,ambiguous

def write_jsonl(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',encoding='utf-8') as f:
  for r in rows:
   if r['text']: f.write(json.dumps(r,ensure_ascii=False)+'\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=ROOT/'nlp/data/raw/public');p.add_argument('--out',type=Path,default=ROOT/'nlp/data/mapped');p.add_argument('--allow-conservative-seracc',action='store_true');args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
 report={"mapping_policy":{"beauty":BEAUTY_MAP,"uit":UIT_MAP,"beauty_others":"exclude/no_aspect (upstream spam)","uit_GENERAL":"exclude","uit_SER&ACC":"manual by default"},"counts":{},"ambiguous":[]}
 for split,bs,us in [('train','beauty_train.csv','uit_train.jsonl'),('dev','beauty_dev.csv','uit_dev.jsonl'),('test','beauty_test.csv','uit_test.jsonl')]:
  rows=[]
  bp=args.raw/bs
  if bp.exists():rows+=beauty(bp,split)
  up=args.raw/us
  if up.exists():
   u,amb=uit(up,split,args.allow_conservative_seracc);rows+=u;report['ambiguous']+=amb
  write_jsonl(args.out/f'{split}.jsonl',rows);report['counts'][split]=len(rows)
 (args.out/'mapping_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({"counts":report['counts'],"ambiguous_SER_ACC":len(report['ambiguous'])},ensure_ascii=False,indent=2))
 print('Mapped data is NOT automatically declared project gold. Human audit + project-specific CSKH/Other annotation remain required.')
if __name__=='__main__':main()
