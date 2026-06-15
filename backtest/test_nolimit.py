
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

def bt(cond):
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

base=(df['zt_Tm2']==1)&(df['是否涨停']==0)&(df['money']>1.5e9)&(df['M7']/df['M14']>1)&df['M14'].notna()
new=base&(df['实体涨跌幅']>-0.03)

print('无仓位限制，每个信号单独算盈亏：')
print()
for name,cond in [('基础',base),('+实体>-3%',new)]:
    t=bt(cond)
    w=sum(1 for x in t if x>0)
    print(f'{name:>10}  信号{len(t):>4}  胜率{w/len(t)*100:5.1f}%  平均{np.mean(t):+.2f}%  最大赚{max(t):+.2f}%  最大亏{min(t):+.2f}%')
