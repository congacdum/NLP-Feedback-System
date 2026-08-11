from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES={
 "beauty_train.csv":"https://raw.githubusercontent.com/linh222/Aspect-based-Sentiment-Analysis-for-Vietnamese-Reviews-about-Beauty-Product-on-E-commerce-Websites/main/data/data_train.csv",
 "beauty_dev.csv":"https://raw.githubusercontent.com/linh222/Aspect-based-Sentiment-Analysis-for-Vietnamese-Reviews-about-Beauty-Product-on-E-commerce-Websites/main/data/data_val.csv",
 "beauty_test.csv":"https://raw.githubusercontent.com/linh222/Aspect-based-Sentiment-Analysis-for-Vietnamese-Reviews-about-Beauty-Product-on-E-commerce-Websites/main/data/data_test.csv",
 "uit_train.jsonl":"https://raw.githubusercontent.com/kimkim00/UIT-ViSD4SA/main/data/train.jsonl",
 "uit_dev.jsonl":"https://raw.githubusercontent.com/kimkim00/UIT-ViSD4SA/main/data/dev.jsonl",
 "uit_test.jsonl":"https://raw.githubusercontent.com/kimkim00/UIT-ViSD4SA/main/data/test.jsonl",
}

def main():
 p=argparse.ArgumentParser();p.add_argument("--out",type=Path,default=ROOT/"nlp/data/raw/public");args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
 for name,url in SOURCES.items():
  target=args.out/name
  if target.exists(): print('exists',target);continue
  print('download',url);urllib.request.urlretrieve(url,target)
 print('Done. Upstream files are intentionally fetched on demand so licensing/provenance stays explicit.')
 print('ViCloABSA is referenced in docs but is not auto-downloaded because a stable official machine-readable distribution URL was not verified in this build.')
if __name__=='__main__':main()
