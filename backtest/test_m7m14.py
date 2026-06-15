import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
import pandas as pd,numpy as np
CSV=r'C:\Users\Administrator\Desktop\全市场A股_2026-04-12_2026-06-12.csv'
df=pd.read_csv(CSV)
df['index']=pd.to_datetime(df['index'])
df.sort_values(['证券代码','index'],inplace=True)
df['M7']=df.groupby('证券代码')['close'].transform(lambda x:x.rolling(7).mean())
df['M14']=df.groupby('证券代码')['close'].transform(lambda x:x.rolling(14).mean())
df['zt_Tm2']=df.groupby('证券代码')['是否涨停'].shift(1)
df['实体涨跌幅']=(df['close']-df['open'])/df['open']

def bt(ratio):
    cond=(df['zt_Tm2']==1)&(df['是否涨停']==0)&(df['money']>1.5e9)&(df['M7']/df['M14']>ratio)&(df['实体涨跌幅']>-0.03)&df['M14'].notna()
    df['sig']=cond.astype(int);t=[]
    for _,row in df[df['sig']==1].iterrows():
        c=row['证券代码'];t1=row['index']
        td=df[(df['证券代码']==c)&(df['index']>t1)]
        if td.empty:continue
        td2=df[(df['证券代码']==c)&(df['index']>td.iloc[0]['index'])]
        if td2.empty:continue
        t.append((td2.iloc[0]['close']-td.iloc[0]['open'])/td.iloc[0]['open']*100)
    return t

print(f'{"M7/M14比值":<12} {"信号总笔数":>8} {"胜率":>8} {"平均盈亏":>10}')
print('-'*42)
for r in [1.0, 1.05, 1.07]:
    t=bt(r);w=sum(1 for x in t if x>0)
    print(f'{r:<12} {len(t):>8} {w/len(t)*100:>7.1f}% {np.mean(t):>+9.2f}%')
