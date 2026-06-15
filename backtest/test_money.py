
import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
import pandas as pd,numpy as np

CSV=r'.\data\全市场A股_2026-04-12_2026-06-12.csv'
df=pd.read_csv(CSV)
df['index']=pd.to_datetime(df['index'])
df.sort_values(['证券代码','index'],inplace=True)
df['M7']=df.groupby('证券代码')['close'].transform(lambda x:x.rolling(7).mean())
df['M14']=df.groupby('证券代码')['close'].transform(lambda x:x.rolling(14).mean())
df['zt_Tm2']=df.groupby('证券代码')['是否涨停'].shift(1)

def bt(money):
    cond=(df['zt_Tm2']==1)&(df['是否涨停']==0)&(df['money']>money)&(df['M7']/df['M14']>1)&df['M14'].notna()
    df['sig']=cond.astype(int)
    r=[]
    for _,row in df[df['sig']==1].iterrows():
        c=row['证券代码'];t1=row['index']
        td=df[(df['证券代码']==c)&(df['index']>t1)]
        if td.empty:continue
        bp=td.iloc[0]['open']
        tp1=df[(df['证券代码']==c)&(df['index']>td.iloc[0]['index'])]
        if tp1.empty:continue
        r.append((tp1.iloc[0]['close']-bp)/bp*100)
    return r

for m,name in [(1.5e9,'15亿'),(2e9,'20亿'),(2.5e9,'25亿'),(3e9,'30亿')]:
    t=bt(m)
    w=sum(1 for x in t if x>0)
    print(f'{name:>4} | 信号{len(t):>4} | 胜率{w/len(t)*100:>5.1f}% | 平均{np.mean(t):>+.2f}%')
